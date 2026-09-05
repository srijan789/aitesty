import time
import json
import shutil
from pathlib import Path
import pytest
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun
from app.core.task_runner import task_runner
from config import TestingConfig

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        task_runner.wait_for_all_tasks(timeout=2.0)
        db.session.remove()
        db.drop_all()
        if Path(app.config["WORKSPACES_ROOT"]).exists():
            shutil.rmtree(app.config["WORKSPACES_ROOT"], ignore_errors=True)

@pytest.fixture
def client(app):
    return app.test_client()

def test_full_exploration_and_test_execution_flow(client, app):
    # 1. Create a project
    res = client.post(
        "/projects",
        data={
            "name": "Integration Store",
            "target_url": "https://store.integration.test",
            "auth_type": "form",
            "auth_username": "testshopper",
            "auth_password": "shopperpassword",
            "scope_instructions": "Explore cart and login",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        proj = Project.query.filter_by(name="Integration Store").first()
        proj_id = proj.id

    # 2. Trigger exploration via API
    res = client.post(f"/api/projects/{proj_id}/explore")
    assert res.status_code == 202
    data = res.get_json()
    assert data["success"] is True
    run_id = data["run_id"]

    # 3. Poll run logs and wait for completion
    completed = False
    for _ in range(40):
        time.sleep(0.15)
        res = client.get(f"/api/runs/{run_id}/logs")
        assert res.status_code == 200
        log_data = res.get_json()
        if log_data["completed"]:
            completed = True
            assert log_data["status"] == "completed"
            assert len(log_data["logs"]) > 0
            break

    assert completed is True, "Exploration run did not complete in time"

    # 4. Verify test plan in DB & on disk
    with app.app_context():
        plan = TestPlan.query.filter_by(project_id=proj_id, status="active").first()
        assert plan is not None
        assert len(plan.test_cases) >= 3

        categories = [tc.category for tc in plan.test_cases]
        assert "happy_path" in categories
        assert "edge_case" in categories
        assert "error_flow" in categories

        # Check workspace files
        ws_root = Path(app.config["WORKSPACES_ROOT"])
        plan_json_path = ws_root / proj_id / "test_plan.json"
        plan_md_path = ws_root / proj_id / "test_plan.md"
        assert plan_json_path.exists()
        assert plan_md_path.exists()

        # Explorer agent does NOT generate .spec.py files (decoupled from script authoring)
        tests_dir = ws_root / proj_id / "tests"
        spec_files = list(tests_dir.glob("*.spec.py")) if tests_dir.exists() else []
        assert len(spec_files) == 0

        # Scenarios have QA attributes and status pending_review
        for tc in plan.test_cases:
            assert tc.status == "pending_review"
            assert tc.priority in ["P0", "P1", "P2", "P3"]
            assert tc.pass_fail_criteria is not None
            assert len(tc.get_steps()) > 0

    # 5. Fetch plan via API
    res = client.get(f"/api/projects/{proj_id}/test-plan")
    assert res.status_code == 200
    plan_json = res.get_json()
    assert len(plan_json["scenarios"]) >= 3
    first_sc = plan_json["scenarios"][0]
    assert first_sc["status"] == "pending_review"

    # 6. Toggle single scenario automation
    first_sc_id = first_sc["id"]
    res = client.post(f"/api/projects/{proj_id}/scenarios/{first_sc_id}/toggle-automation")
    assert res.status_code == 200
    toggle_data = res.get_json()
    assert toggle_data["success"] is True
    assert toggle_data["new_status"] == "marked_for_automation"

    with app.app_context():
        tc_db = db.session.get(TestCase, first_sc_id)
        assert tc_db.status == "marked_for_automation"

    # 7. Bulk mark all scenarios for automation
    res = client.post(
        f"/api/projects/{proj_id}/scenarios/bulk-mark-automation",
        data=json.dumps({"status": "marked_for_automation"}),
        content_type="application/json"
    )
    assert res.status_code == 200
    bulk_data = res.get_json()
    assert bulk_data["success"] is True
    assert bulk_data["updated_count"] >= 3

    with app.app_context():
        all_cases = TestCase.query.filter_by(test_plan_id=plan.id).all()
        assert all(tc.status == "marked_for_automation" for tc in all_cases)

    # 8. Update plan via API (edit QA scenario fields)
    plan_json["scenarios"][0]["title"] = "Updated Custom QA Scenario"
    plan_json["scenarios"][0]["priority"] = "P0"
    plan_json["scenarios"][0]["pass_fail_criteria"] = "1. Must return HTTP 200\n2. Header must display welcome"
    res = client.put(
        f"/api/projects/{proj_id}/test-plan",
        data=json.dumps(plan_json),
        content_type="application/json",
    )
    assert res.status_code == 200

    with app.app_context():
        updated_plan = TestPlan.query.filter_by(project_id=proj_id, status="active").first()
        assert updated_plan.test_cases[0].title == "Updated Custom QA Scenario"
        assert updated_plan.test_cases[0].priority == "P0"

    # 9. Trigger test execution when no spec files exist yet -> completes cleanly with warning
    res = client.post(f"/api/projects/{proj_id}/execute-tests")
    assert res.status_code == 202
    test_run_id = res.get_json()["run_id"]

    test_completed = False
    for _ in range(40):
        time.sleep(0.15)
        res = client.get(f"/api/runs/{test_run_id}/status")
        run_status = res.get_json()
        if run_status["status"] in ["completed", "failed"]:
            test_completed = True
            assert run_status["status"] == "completed"
            assert run_status["summary_stats"]["total"] == 0
            break

    assert test_completed is True, "Test execution run did not complete in time"


def test_delete_scenario_and_delete_test_file(client, app):
    # 1. Setup project, plan, test cases, and file
    with app.app_context():
        project = Project(name="Delete Test Project", target_url="http://localhost:5000", auth_type="none")
        db.session.add(project)
        db.session.commit()
        project_id = project.id

        plan = TestPlan(project_id=project_id, version=1, status="active", summary="Delete Test Plan")
        db.session.add(plan)
        db.session.flush()

        tc1 = TestCase(
            test_plan_id=plan.id,
            title="Keep Scenario",
            category="happy_path",
            status="automated",
            script_path="tests/test_demo.spec.py",
        )
        tc2 = TestCase(
            test_plan_id=plan.id,
            title="Delete Scenario",
            category="edge_case",
            status="pending_review",
        )
        db.session.add_all([tc1, tc2])
        db.session.commit()
        tc1_id = tc1.id
        tc2_id = tc2.id
        plan_dict = plan.to_dict()

    # Create test file on disk
    from app.core.workspace import WorkspaceManager
    wm = WorkspaceManager(Path(app.config["WORKSPACES_ROOT"]))
    wm.save_test_file(project_id, "tests/test_demo.spec.py", "def test_demo(): pass")
    wm.save_test_plan(project_id, plan_dict)

    # 2. Delete scenario tc2 via API
    res_del_sc = client.delete(f"/api/projects/{project_id}/scenarios/{tc2_id}")
    assert res_del_sc.status_code == 200
    data_sc = res_del_sc.get_json()
    assert data_sc["success"] is True
    assert data_sc["remaining_scenarios_count"] == 1

    with app.app_context():
        assert db.session.get(TestCase, tc2_id) is None
        assert db.session.get(TestCase, tc1_id) is not None

    # Check updated test_plan.json on disk
    disk_plan = wm.load_test_plan_json(project_id)
    assert len(disk_plan["scenarios"]) == 1
    assert disk_plan["scenarios"][0]["title"] == "Keep Scenario"

    # 3. Test invalid file deletion attempts (security checks)
    res_traversal = client.delete(f"/api/projects/{project_id}/files?path=../config.json")
    assert res_traversal.status_code == 400

    res_missing = client.delete(f"/api/projects/{project_id}/files?path=tests/non_existent.py")
    assert res_missing.status_code == 404

    # 4. Valid test file deletion
    res_del_file = client.delete(f"/api/projects/{project_id}/files?path=tests/test_demo.spec.py")
    assert res_del_file.status_code == 200
    data_file = res_del_file.get_json()
    assert data_file["success"] is True

    # Verify file is deleted on disk
    file_path = Path(app.config["WORKSPACES_ROOT"]) / project_id / "tests" / "test_demo.spec.py"
    assert not file_path.exists()

    # Verify linked TestCase is updated
    with app.app_context():
        updated_tc1 = db.session.get(TestCase, tc1_id)
        assert updated_tc1.script_path is None
        assert updated_tc1.status == "marked_for_automation"


def test_bulk_delete_scenarios_and_files(client, app):
    with app.app_context():
        p = Project(name="Bulk Project", target_url="http://example.com", auth_type="none")
        db.session.add(p)
        db.session.commit()
        project_id = p.id

        plan = TestPlan(project_id=project_id, version=1, status="active")
        db.session.add(plan)
        db.session.flush()

        tc1 = TestCase(test_plan_id=plan.id, title="Scenario 1", category="happy_path", status="pending_review")
        tc2 = TestCase(test_plan_id=plan.id, title="Scenario 2", category="edge_case", status="pending_review")
        tc3 = TestCase(test_plan_id=plan.id, title="Scenario 3", category="error_flow", status="pending_review")
        db.session.add_all([tc1, tc2, tc3])
        db.session.commit()
        tc1_id = tc1.id
        tc2_id = tc2.id
        tc3_id = tc3.id

    from app.core.workspace import WorkspaceManager
    wm = WorkspaceManager(Path(app.config["WORKSPACES_ROOT"]))
    wm.save_test_file(project_id, "tests/test_file1.spec.py", "def test_1(): pass")
    wm.save_test_file(project_id, "tests/test_file2.spec.py", "def test_2(): pass")

    # 1. Bulk delete scenarios (tc2 and tc3)
    res_sc = client.post(
        f"/api/projects/{project_id}/scenarios/bulk-delete",
        json={"scenario_ids": [tc2_id, tc3_id]}
    )
    assert res_sc.status_code == 200
    data_sc = res_sc.get_json()
    assert data_sc["success"] is True
    assert data_sc["deleted_count"] == 2
    assert data_sc["remaining_scenarios_count"] == 1

    with app.app_context():
        assert db.session.get(TestCase, tc1_id) is not None
        assert db.session.get(TestCase, tc2_id) is None
        assert db.session.get(TestCase, tc3_id) is None

    # 2. Bulk delete test files
    res_f = client.post(
        f"/api/projects/{project_id}/files/bulk-delete",
        json={"paths": ["tests/test_file1.spec.py", "tests/test_file2.spec.py"]}
    )
    assert res_f.status_code == 200
    data_f = res_f.get_json()
    assert data_f["success"] is True
    assert data_f["deleted_count"] == 2

    # Verify files deleted on disk
    ws_tests = Path(app.config["WORKSPACES_ROOT"]) / project_id / "tests"
    assert not (ws_tests / "test_file1.spec.py").exists()
    assert not (ws_tests / "test_file2.spec.py").exists()

    # 3. Targeted test execution with target_files and test_names
    res_exec = client.post(
        f"/api/projects/{project_id}/execute-tests",
        json={
            "target_files": ["tests/test_a.spec.py", "tests/test_b.spec.py"],
            "test_names": ["test_01_navigate", "test_02_interaction"]
        }
    )
    assert res_exec.status_code == 202
    data_exec = res_exec.get_json()
    assert data_exec["success"] is True
    assert data_exec["target_files"] == ["tests/test_a.spec.py", "tests/test_b.spec.py"]
    assert data_exec["target_tests"] == ["test_01_navigate", "test_02_interaction"]

def test_headless_and_slow_mo_api_options(client, app):
    # Create project
    res = client.post(
        "/projects",
        data={
            "name": "Headed Mode Project",
            "target_url": "https://example.com",
            "auth_type": "none",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        proj = Project.query.filter_by(name="Headed Mode Project").first()
        proj_id = proj.id

    # 1. Trigger exploration with headed=True (headless=False) and slow_mo=500
    res_exp = client.post(
        f"/api/projects/{proj_id}/explore",
        json={"headless": False, "slow_mo": 500},
    )
    assert res_exp.status_code == 202
    data_exp = res_exp.get_json()
    assert data_exp["success"] is True
    assert "run_id" in data_exp

    # 2. Trigger test execution with headless=False and slow_mo=500
    res_exec = client.post(
        f"/api/projects/{proj_id}/execute-tests",
        json={"headless": False, "slow_mo": 500},
    )
    assert res_exec.status_code == 202
    data_exec = res_exec.get_json()
    assert data_exec["success"] is True
    assert "run_id" in data_exec

    task_runner.wait_for_all_tasks(timeout=5.0)



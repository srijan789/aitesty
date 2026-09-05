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
from config import TestingConfig

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
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

<<<<<<< HEAD
        # The Planner no longer writes test files itself -- that's the Generator stage's job,
        # so the workspace tests/ dir stays empty after exploration alone.
        assert list((ws_root / proj_id / "tests").glob("*")) == []
=======
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
>>>>>>> 145374c (Added the Exploratory + test planning agent)

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

<<<<<<< HEAD
    # 7. Trigger test execution run -- no test files exist yet since the standalone "Explore
    #    Now" flow only runs the Planner; generating executable specs is the Generator stage's
    #    job (exercised together with the rest of the pipeline in test_pipeline_orchestrator.py).
=======
    # 9. Trigger test execution when no spec files exist yet -> completes cleanly with warning
>>>>>>> 145374c (Added the Exploratory + test planning agent)
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
<<<<<<< HEAD
            stats = run_status["summary_stats"]
            assert stats["total"] == 0
            assert stats["passed"] == 0
=======
            assert run_status["summary_stats"]["total"] == 0
>>>>>>> 145374c (Added the Exploratory + test planning agent)
            break

    assert test_completed is True, "Test execution run did not complete in time"


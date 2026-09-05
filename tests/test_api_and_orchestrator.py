import time
import json
import shutil
from pathlib import Path
import pytest
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan
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

        # Check generated test script
        test_file = ws_root / proj_id / "tests" / "test_auth_flow.spec.py"
        assert test_file.exists()
        assert "Autonomous Generated Playwright Test Suite" in test_file.read_text()

    # 5. Fetch plan via API
    res = client.get(f"/api/projects/{proj_id}/test-plan")
    assert res.status_code == 200
    plan_json = res.get_json()
    assert len(plan_json["scenarios"]) >= 3

    # 6. Update plan via API (edit a scenario)
    plan_json["scenarios"][0]["title"] = "Updated Custom Scenario Title"
    res = client.put(
        f"/api/projects/{proj_id}/test-plan",
        data=json.dumps(plan_json),
        content_type="application/json",
    )
    assert res.status_code == 200

    with app.app_context():
        updated_plan = TestPlan.query.filter_by(project_id=proj_id, status="active").first()
        assert updated_plan.test_cases[0].title == "Updated Custom Scenario Title"

    # 7. Trigger test execution run
    res = client.post(f"/api/projects/{proj_id}/execute-tests")
    assert res.status_code == 202
    test_run_id = res.get_json()["run_id"]

    # 8. Wait for test run to finish
    test_completed = False
    for _ in range(40):
        time.sleep(0.15)
        res = client.get(f"/api/runs/{test_run_id}/status")
        run_status = res.get_json()
        if run_status["status"] in ["completed", "failed"]:
            test_completed = True
            assert run_status["status"] == "completed"
            stats = run_status["summary_stats"]
            assert stats["passed"] >= 2
            assert stats["failed"] == 0
            break

    assert test_completed is True, "Test execution run did not complete in time"

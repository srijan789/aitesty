import json
import pytest
import shutil
from pathlib import Path
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun, RunLog
from app.core.workspace import WorkspaceManager
from app.core.test_runner import TestRunner
from config import TestingConfig

class DummyProject:
    def __init__(self, id, name, target_url):
        self.id = id
        self.name = name
        self.description = "Test Desc"
        self.target_url = target_url
        self.auth_type = "form"
        self.scope_instructions = "Test scope"
        self.created_at = None

    def get_credentials(self):
        return {"username": "admin", "password": "pwd"}

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        if Path(app.config["WORKSPACES_ROOT"]).exists():
            shutil.rmtree(app.config["WORKSPACES_ROOT"], ignore_errors=True)

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def temp_ws(tmp_path):
    ws = WorkspaceManager(tmp_path / "workspaces")
    yield ws
    shutil.rmtree(tmp_path / "workspaces", ignore_errors=True)

def test_workspace_isolated_test_logs(temp_ws):
    proj = DummyProject("proj-isolated", "Isolated App", "https://app.test")
    temp_ws.init_project_workspace(proj)
    temp_ws.init_run_dir("proj-isolated", "run-101")

    # Append to test_login
    temp_ws.append_test_log_file("proj-isolated", "run-101", "test_login", "INFO", "Navigating to /login")
    temp_ws.append_test_log_file("proj-isolated", "run-101", "test_login", "DEBUG", "Found #username field")

    # Append to test_checkout
    temp_ws.append_test_log_file("proj-isolated", "run-101", "test_checkout", "INFO", "Navigating to /checkout")
    temp_ws.append_test_log_file("proj-isolated", "run-101", "test_checkout", "ERROR", "Payment button timed out")

    # Verify test_login log
    login_log = temp_ws.read_test_log_file("proj-isolated", "run-101", "test_login")
    assert "Navigating to /login" in login_log
    assert "Found #username field" in login_log
    assert "checkout" not in login_log

    # Verify test_checkout log
    checkout_log = temp_ws.read_test_log_file("proj-isolated", "run-101", "test_checkout")
    assert "Navigating to /checkout" in checkout_log
    assert "Payment button timed out" in checkout_log
    assert "Navigating to /login" not in checkout_log

    # List files
    log_files = temp_ws.list_test_log_files("proj-isolated", "run-101")
    assert "test_login" in log_files
    assert "test_checkout" in log_files

def test_runlog_db_model_isolated_tags(app):
    with app.app_context():
        proj = Project(name="Tag App", target_url="https://app.test")
        db.session.add(proj)
        db.session.commit()

        run = TestRun(project_id=proj.id, run_type="execution", status="running")
        db.session.add(run)
        db.session.commit()

        log1 = RunLog(
            run_id=run.id,
            level="INFO",
            message="Step 1 for login",
            test_name="test_login_flow",
            scenario_id="sc-001"
        )
        log2 = RunLog(
            run_id=run.id,
            level="ERROR",
            message="Step 1 for checkout failed",
            test_name="test_checkout_flow",
            scenario_id="sc-002"
        )
        db.session.add_all([log1, log2])
        db.session.commit()

        login_logs = RunLog.query.filter_by(run_id=run.id, test_name="test_login_flow").all()
        assert len(login_logs) == 1
        assert login_logs[0].message == "Step 1 for login"
        assert login_logs[0].scenario_id == "sc-001"

        d = login_logs[0].to_dict()
        assert d["test_name"] == "test_login_flow"
        assert d["scenario_id"] == "sc-001"

def test_api_isolated_testcases_and_logs(client, app):
    with app.app_context():
        proj = Project(name="API Log App", target_url="https://app.test")
        db.session.add(proj)
        db.session.commit()

        run = TestRun(project_id=proj.id, run_type="execution", status="completed")
        db.session.add(run)
        db.session.commit()

        # Add RunLog entries
        log_entry = RunLog(
            run_id=run.id,
            level="INFO",
            message="Executing step: Click submit",
            test_name="test_payment",
            scenario_id="sc-pay"
        )
        db.session.add(log_entry)
        db.session.commit()

        ws = WorkspaceManager(Path(app.config["WORKSPACES_ROOT"]))
        ws.init_project_workspace(proj)
        ws.init_run_dir(proj.id, run.id)

        # Write results.json
        results_data = {
            "summary": {"total": 1, "passed": 0, "failed": 1},
            "tests": [
                {
                    "test_name": "test_payment",
                    "scenario_id": "sc-pay",
                    "status": "failed",
                    "duration_ms": 1400,
                    "error_message": "Timeout 5000ms exceeded",
                    "failure_classification": "AUTOMATION_FAILURE"
                }
            ]
        }
        ws.save_run_results(proj.id, run.id, results_data)

        # Write isolated log file
        ws.append_test_log_file(
            proj.id,
            run.id,
            "test_payment",
            "INFO",
            "=== TESTCASE ISOLATED EXECUTION LOG: test_payment ==="
        )
        ws.append_test_log_file(
            proj.id,
            run.id,
            "test_payment",
            "ERROR",
            "Timeout 5000ms exceeded waiting for locator('#pay-button')"
        )

        proj_id = proj.id
        run_id = run.id

    # Test GET /api/runs/<run_id>/testcases
    res = client.get(f"/api/runs/{run_id}/testcases")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["testcases"]) == 1
    tc = data["testcases"][0]
    assert tc["test_name"] == "test_payment"
    assert tc["status"] == "failed"
    assert tc["has_isolated_log"] is True

    # Test GET /api/runs/<run_id>/testcases/test_payment/logs
    res = client.get(f"/api/runs/{run_id}/testcases/test_payment/logs")
    assert res.status_code == 200
    log_data = res.get_json()
    assert log_data["success"] is True
    assert log_data["test_name"] == "test_payment"
    assert log_data["log_file_found"] is True
    assert "Timeout 5000ms exceeded waiting for locator" in log_data["raw_log"]
    assert len(log_data["structured_logs"]) == 1
    assert log_data["telemetry"]["failure_classification"] == "AUTOMATION_FAILURE"

    # Test GET logs for non-existent test
    res = client.get(f"/api/runs/{run_id}/testcases/nonexistent_test/logs")
    assert res.status_code == 200
    missing_data = res.get_json()
    assert missing_data["log_file_found"] is False
    assert missing_data["raw_log"] == ""

    # Test GET /projects/<project_id>/runs/<run_id> HTML view rendering
    html_res = client.get(f"/projects/{proj_id}/runs/{run_id}")
    assert html_res.status_code == 200
    html_text = html_res.get_data(as_text=True)
    assert "Analyze & Heal Run" in html_text
    assert "API Log App" in html_text
    assert "Isolated Testcase Logs" in html_text


import pytest
import shutil
from pathlib import Path
from app.core.workspace import WorkspaceManager

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
def temp_ws(tmp_path):
    ws = WorkspaceManager(tmp_path / "workspaces")
    yield ws
    shutil.rmtree(tmp_path / "workspaces", ignore_errors=True)

def test_workspace_initialization(temp_ws):
    proj = DummyProject("proj-123", "Test App", "https://app.test")
    p_dir = temp_ws.init_project_workspace(proj)
    assert p_dir.exists()
    assert (p_dir / "config.json").exists()
    assert (p_dir / "tests").exists()
    assert (p_dir / "runs").exists()

    cfg = temp_ws.get_project_config("proj-123")
    assert cfg["name"] == "Test App"
    assert cfg["credentials"]["username"] == "admin"

def test_test_plan_persistence(temp_ws):
    proj = DummyProject("proj-plan", "Plan App", "https://plan.test")
    temp_ws.init_project_workspace(proj)

    plan_data = {
        "version": 1,
        "summary": "Exploration Plan",
        "scenarios": [
            {
                "title": "Login Test",
                "category": "happy_path",
                "description": "User logs in",
                "steps": [{"action": "click", "target_element": "btn"}],
                "expected_result": "Success",
            }
        ]
    }
    temp_ws.save_test_plan("proj-plan", plan_data)

    loaded = temp_ws.load_test_plan_json("proj-plan")
    assert loaded["version"] == 1
    assert len(loaded["scenarios"]) == 1
    assert loaded["scenarios"][0]["title"] == "Login Test"

    md = temp_ws.load_test_plan_md("proj-plan")
    assert "Login Test" in md
    assert "Happy Path" in md

def test_run_directory_and_log_append(temp_ws):
    proj = DummyProject("proj-run", "Run App", "https://run.test")
    temp_ws.init_project_workspace(proj)

    run_dir = temp_ws.init_run_dir("proj-run", "run-001")
    assert run_dir.exists()
    assert (run_dir / "execution.log").exists()

    temp_ws.append_run_log_file("proj-run", "run-001", "INFO", "Hello live log")
    logs = temp_ws.read_run_log_file("proj-run", "run-001")
    assert "Hello live log" in logs
    assert "[INFO]" in logs

def test_path_traversal_prevention(temp_ws):
    with pytest.raises(ValueError):
        temp_ws.get_project_dir("../../../etc")

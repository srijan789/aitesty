import json
import pytest
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun
from app.core.orchestrator import TestOrchestrator
from app.agents.base import GeneratorConfig
from app.agents.mock_generator import MockGeneratorAgent
from app.agents.playwright_generator import PlaywrightGeneratorAgent

@pytest.fixture
def app():
    app = create_app("config.TestingConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_mock_generator_agent(app, tmp_path):
    agent = MockGeneratorAgent()
    scenarios = [
        {"id": "sc-1", "title": "Login Happy Path", "category": "happy_path", "steps": []},
        {"id": "sc-2", "title": "Boundary Input", "category": "edge_case", "steps": []},
    ]
    config = GeneratorConfig(
        project_id="test-proj",
        target_url="http://localhost:5000",
        auth_type="none",
        credentials={},
        workspace_dir=str(tmp_path),
        run_id="run-1",
        scenarios=scenarios,
    )
    logs = []
    result = agent.generate(config, lambda lvl, msg, meta=None: logs.append(msg))
    assert result.status == "success"
    assert len(result.generated_files) == 1
    assert "tests/test_mock_suite.spec.py" in result.generated_files[0].relative_path
    assert (tmp_path / "tests" / "test_mock_suite.spec.py").exists()

def test_playwright_generator_fallback_synthesizer(tmp_path):
    agent = PlaywrightGeneratorAgent()
    scenarios = [
        {
            "id": "sc-auth",
            "title": "User Authentication",
            "category": "happy_path",
            "preconditions": "Clean session",
            "pass_fail_criteria": "HTTP 200 and dashboard visible",
            "expected_result": "Redirect to dashboard",
            "steps": [
                {"step_number": 1, "action": "Navigate", "target_element": "http://localhost:5000/login", "expected_outcome": "Login page loaded"},
                {"step_number": 2, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": "admin"},
                {"step_number": 3, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Submitted"},
            ]
        }
    ]
    config = GeneratorConfig(
        project_id="test-proj-2",
        target_url="http://localhost:5000",
        auth_type="basic",
        credentials={"username": "admin"},
        workspace_dir=str(tmp_path),
        run_id="run-2",
        scenarios=scenarios,
    )
    code = agent._synthesize_code_fallback(config, "happy_path", scenarios)
    assert "def test_user_authentication" in code
    assert "page.goto" in code
    assert "page.locator" in code
    assert "TARGET_URL" in code

def test_orchestrator_trigger_test_generation(app):
    with app.app_context():
        # Create project and plan with marked scenario
        project = Project(
            name="Gen Test Project",
            target_url="http://localhost:5000",
            auth_type="none",
        )
        db.session.add(project)
        db.session.commit()

        plan = TestPlan(
            project_id=project.id,
            version=1,
            status="active",
            summary="Test Plan",
        )
        db.session.add(plan)
        db.session.flush()

        tc1 = TestCase(
            test_plan_id=plan.id,
            title="Marked Scenario 1",
            category="happy_path",
            status="marked_for_automation",
        )
        tc1.set_steps([{"step_number": 1, "action": "Navigate", "target_element": "http://localhost:5000"}])
        tc2 = TestCase(
            test_plan_id=plan.id,
            title="Pending Scenario 2",
            category="edge_case",
            status="pending_review",
        )
        db.session.add_all([tc1, tc2])
        db.session.commit()

        # Trigger test generation
        run = TestOrchestrator.trigger_test_generation(project.id)
        assert run.run_type == "test_generation"
        assert run.status in ["queued", "running", "completed"]

        # Wait for task runner
        import time
        for _ in range(20):
            db.session.refresh(run)
            if run.status in ["completed", "failed"]:
                break
            time.sleep(0.1)

        assert run.status == "completed"
        db.session.refresh(tc1)
        assert tc1.status == "automated"
        assert tc1.script_path is not None

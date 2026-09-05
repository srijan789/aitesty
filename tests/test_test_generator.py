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
        from app.core.task_runner import task_runner
        task_runner.wait_for_all_tasks(timeout=3.0)
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
    assert "def test_01_navigate_and_view_user_authentication" in code
    assert "def test_02_interaction_and_validation_user_authentication" in code
    assert "def test_03_action_and_outcome_user_authentication" in code
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
        from app.core.task_runner import task_runner
        task_runner.wait_for_all_tasks(timeout=3.0)
        db.session.refresh(tc1)
        assert tc1.status == "automated"
        assert tc1.script_path is not None
        stats = run.get_summary_stats()
        assert stats.get("subtests_created") == 1
        assert len(stats.get("subtests_per_test", [])) == 1
        assert stats["subtests_per_test"][0]["subtests_count"] == 1


def test_subtest_generation_and_metadata(tmp_path):
    agent = PlaywrightGeneratorAgent()
    scenarios = [
        {
            "id": "sc-checkout",
            "title": "Checkout Payment Flow",
            "category": "happy_path",
            "preconditions": "Cart has items",
            "pass_fail_criteria": "Order confirmation message displayed",
            "expected_result": "Order confirmed",
            "steps": [
                {"step_number": 1, "action": "Navigate", "target_element": "http://localhost:5000/checkout", "expected_outcome": "Checkout page loaded"},
                {"step_number": 2, "action": "Fill", "target_element": "#card-number", "expected_outcome": "4242..."},
                {"step_number": 3, "action": "Click", "target_element": "#pay-btn", "expected_outcome": "Payment submitted"},
            ]
        }
    ]
    config = GeneratorConfig(
        project_id="test-proj-subtests",
        target_url="http://localhost:5000",
        auth_type="none",
        credentials={},
        workspace_dir=str(tmp_path),
        run_id="run-subtests-1",
        scenarios=scenarios,
    )
    res = agent.generate(config, lambda lvl, msg, meta=None: None)
    assert res.status == "success"
    assert len(res.generated_files) == 1
    gen_file = res.generated_files[0]
    assert gen_file.subtest_count == 3

    # Check file contents and subtest functions
    full_path = tmp_path / gen_file.relative_path
    assert full_path.exists()
    content = full_path.read_text(encoding="utf-8")
    assert "def test_01_navigate_and_view_" in content
    assert "def test_02_interaction_and_validation_" in content
    assert "def test_03_action_and_outcome_" in content
    assert "Scenario ID: sc-checkout" in content

    # Test AST parsing via TestRunner
    from app.core.test_runner import TestRunner
    runner = TestRunner(str(tmp_path), "test-proj-subtests", "run-1", "http://localhost:5000")
    subtests = runner.extract_test_functions_from_file(full_path)
    assert len(subtests) == 3
    assert subtests[0]["name"].startswith("test_01_navigate_and_view_")
    assert subtests[0]["scenario_id"] == "sc-checkout"
    assert subtests[1]["name"].startswith("test_02_interaction_and_validation_")
    assert subtests[2]["name"].startswith("test_03_action_and_outcome_")

    # Test WorkspaceManager.list_test_files includes subtests
    from app.core.workspace import WorkspaceManager
    wm = WorkspaceManager(tmp_path.parent)
    # create directory structure matching workspace_dir / project_id
    project_dir = tmp_path.parent / "test-proj-subtests"
    project_dir.mkdir(parents=True, exist_ok=True)
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(full_path, tests_dir / full_path.name)

    files = wm.list_test_files("test-proj-subtests")
    assert len(files) == 1
    assert len(files[0]["subtests"]) == 3
    assert files[0]["subtests"][0]["name"].startswith("test_01_navigate_and_view_")

import json
import time
import pytest
import shutil
from pathlib import Path
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun
from app.agents.base import HealingConfig, GeneratorConfig, FailedCaseAnalysis, HealingResult
from app.agents.mock_healer import MockHealingAgent
from app.agents.healing_agent import PlaywrightHealingAgent
from app.agents.playwright_generator import PlaywrightGeneratorAgent
from app.core.workspace import WorkspaceManager
from config import TestingConfig

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

def test_mock_healing_agent():
    agent = MockHealingAgent()
    cfg = HealingConfig(
        project_id="proj-mock",
        target_url="https://app.mock",
        workspace_dir="/tmp/mock_ws",
        run_ids=["run-mock-1"]
    )

    logs = []
    def log_cb(lvl, msg, meta=None):
        logs.append((lvl, msg))

    result = agent.analyze_and_heal(cfg, log_callback=log_cb)
    assert isinstance(result, HealingResult)
    assert result.status == "success"
    assert "run-mock-1" in result.analyzed_runs
    assert result.failed_cases_analyzed >= 2
    assert len(result.analyses) >= 2

    # Verify first analysis (automation failure)
    a1 = next(a for a in result.analyses if a.failure_origin == "AUTOMATION_FAILURE")
    assert a1.verdict == "NEEDS_FIX"
    assert "selector" in a1.notes_for_generator.lower() or "button" in a1.notes_for_generator.lower()

    # Verify second analysis (product defect)
    a2 = next(a for a in result.analyses if a.failure_origin == "PRODUCT_DEFECT")
    assert a2.verdict == "REAL_BUG"
    assert "defect" in a2.notes_for_planner.lower() or "500" in a2.notes_for_planner

def test_playwright_healing_heuristics_classification():
    # Test fallback heuristics when LLM is offline
    agent = PlaywrightHealingAgent(model="test-model")

    # Case 1: Automation Failure - Locator Timeout
    analysis_auto = agent._heuristic_diagnosis(
        test_data={"test_name": "test_login_submit", "scenario_id": "sc-login", "scenario_title": "Login with valid credentials"},
        error_message="playwright._impl._errors.TimeoutError: Page.click: Timeout 5000ms exceeded waiting for locator('button.submit')",
        traceback_str="Traceback ... Page.click ... Timeout 5000ms",
        classification_data={"classification": "AUTOMATION_FAILURE", "subtype": "LOCATOR_TIMEOUT"},
        candidates=[],
        network_events=[],
        console_messages=[],
    )
    assert analysis_auto.failure_origin == "AUTOMATION_FAILURE"
    assert analysis_auto.verdict == "NEEDS_FIX"
    assert "locator" in analysis_auto.notes_for_generator.lower() or "button" in analysis_auto.notes_for_generator.lower()
    assert analysis_auto.root_cause != ""

    # Case 2: Product Defect - HTTP 500 Server Error
    analysis_defect = agent._heuristic_diagnosis(
        test_data={"test_name": "test_order_placement", "scenario_id": "sc-order", "scenario_title": "Place new order"},
        error_message="Expected status 200 but got 500 Internal Server Error",
        traceback_str="AssertionError: 500 != 200",
        classification_data={"classification": "APP_DEFECT", "subtype": "HTTP_SERVER_ERROR"},
        candidates=[],
        network_events=[{"status": 500, "url": "/api/orders"}],
        console_messages=[],
    )
    assert analysis_defect.failure_origin == "PRODUCT_DEFECT"
    assert analysis_defect.verdict == "REAL_BUG"
    assert "bug" in analysis_defect.notes_for_planner.lower() or "defect" in analysis_defect.notes_for_planner.lower()

    # Case 3: Invalid Testcase - Deprecated or 404 Route
    analysis_invalid = agent._heuristic_diagnosis(
        test_data={"test_name": "test_legacy_feature", "scenario_id": "sc-legacy", "scenario_title": "Access deprecated settings"},
        error_message="HTTP 404 Not Found: Page removed or deprecated",
        traceback_str="Error: 404 Not Found",
        classification_data={"classification": "APP_DEFECT", "subtype": "HTTP_CLIENT_ERROR"},
        candidates=[],
        network_events=[{"status": 404, "url": "/legacy/settings"}],
        console_messages=[],
    )
    assert analysis_invalid.verdict == "INVALID_TESTCASE"
    assert "invalid" in analysis_invalid.notes_for_planner.lower() or "obsolete" in analysis_invalid.notes_for_planner.lower()

def test_generator_prompt_incorporates_healing_notes():
    generator = PlaywrightGeneratorAgent()
    gen_config = GeneratorConfig(
        project_id="p-test",
        target_url="https://shop.test",
        auth_type="none",
        credentials={},
        scope_instructions="Test shop",
        workspace_dir="/tmp/p-test",
        run_id="run-gen"
    )
    scenarios = [
        {
            "id": "sc-001",
            "title": "Add to Cart",
            "category": "happy_path",
            "description": "Add an item to the shopping cart",
            "steps": [{"action": "click", "target_element": "button#add-to-cart"}],
            "expected_result": "Cart count increases",
            "healing_notes": "CRITICAL FIX: #add-to-cart locator changed to button[data-test='add-item']. Use data-test selector.",
            "healing_status": "needs_fix"
        }
    ]

    prompt = generator._build_generation_prompt(
        config=gen_config,
        category="happy_path",
        scenarios=scenarios
    )

    assert "CRITICAL FIX: #add-to-cart locator changed" in prompt
    assert "Healing & Diagnostic Guidance" in prompt

def test_healing_api_flow(client, app):
    with app.app_context():
        # Setup project, test plan with testcases, and test run
        proj = Project(name="Heal Test Project", target_url="https://demo.test")
        db.session.add(proj)
        db.session.commit()

        plan = TestPlan(
            project_id=proj.id,
            version=1,
            summary="Test Suite for Healing"
        )
        db.session.add(plan)
        db.session.commit()

        tc = TestCase(
            test_plan_id=plan.id,
            title="Cart Checkout",
            category="happy_path",
            steps_json=json.dumps([{"action": "click", "target_element": "#checkout"}])
        )
        db.session.add(tc)
        db.session.commit()

        run = TestRun(project_id=proj.id, run_type="execution", status="failed")
        db.session.add(run)
        db.session.commit()

        ws = WorkspaceManager(Path(app.config["WORKSPACES_ROOT"]))
        ws.init_project_workspace(proj)
        ws.init_run_dir(proj.id, run.id)

        # Write run results with 1 failure
        results_data = {
            "summary": {"total": 1, "passed": 0, "failed": 1},
            "tests": [
                {
                    "test_name": "test_cart_checkout",
                    "scenario_id": tc.id,
                    "status": "failed",
                    "duration_ms": 2500,
                    "error_message": "Timeout 5000ms waiting for locator('#checkout')",
                    "traceback": "Traceback ... TimeoutError: locator('#checkout')",
                    "failure_classification": "AUTOMATION_FAILURE",
                    "subtype": "LOCATOR_TIMEOUT"
                }
            ]
        }
        ws.save_run_results(proj.id, run.id, results_data)

        # Write test log
        ws.append_test_log_file(
            proj.id,
            run.id,
            "test_cart_checkout",
            "ERROR",
            "Timeout 5000ms waiting for locator('#checkout')"
        )

        proj_id = proj.id
        run_id = run.id
        tc_id = tc.id

    # Trigger Healing API
    res = client.post(f"/api/projects/{proj_id}/heal", json={"run_ids": [run_id]})
    assert res.status_code == 202
    data = res.get_json()
    assert data["success"] is True
    heal_run_id = data["run_id"]

    # Poll until healing finishes
    for _ in range(40):
        time.sleep(0.2)
        res = client.get(f"/api/runs/{heal_run_id}/logs")
        if res.status_code == 200:
            log_data = res.get_json()
            if log_data["status"] in ("completed", "failed"):
                break

    # Check healing report via API
    res = client.get(f"/api/runs/{run_id}/healing")
    assert res.status_code == 200
    report_data = res.get_json()
    assert report_data["success"] is True
    report = report_data["report"]
    assert report["run_id"] == run_id
    assert report["total_failed"] == 1
    assert len(report["analyses"]) == 1
    analysis = report["analyses"][0]
    assert analysis["failure_origin"] == "AUTOMATION_FAILURE"
    assert analysis["verdict"] == "NEEDS_FIX"

    # Verify TestCase database model was updated with healing notes
    with app.app_context():
        updated_tc = db.session.get(TestCase, tc_id)
        assert updated_tc is not None
        assert updated_tc.healing_status == "needs_script_fix"
        assert updated_tc.healing_notes != ""
        assert "locator" in updated_tc.healing_notes.lower()

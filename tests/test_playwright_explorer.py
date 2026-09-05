import json
import shutil
from pathlib import Path
import pytest

from app import create_app
from app.extensions import db
from app.models.project import Project
from app.agents.base import ExplorerConfig, ExplorerResult, DiscoveredScenario
from app.agents.playwright_controller import PlaywrightController
from app.agents.playwright_explorer import PlaywrightExplorerAgent
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

def test_project_model_with_prd(app, client):
    prd_sample = """
    # PRD: User Checkout Flow
    Requirement 1: User can add item to cart.
    Requirement 2: Cart total calculates 10% tax.
    Requirement 3: Payment rejection displays alert banner.
    """
    res = client.post(
        "/projects",
        data={
            "name": "E-Commerce App",
            "target_url": "https://store.example.com",
            "prd_text": prd_sample,
            "auth_type": "none",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        project = Project.query.filter_by(name="E-Commerce App").first()
        assert project is not None
        assert project.prd_text == prd_sample.strip()
        p_dict = project.to_dict()
        assert p_dict["prd_text"] == prd_sample.strip()

        # Check config.json on disk
        ws_root = Path(app.config["WORKSPACES_ROOT"])
        cfg_file = ws_root / project.id / "config.json"
        assert cfg_file.exists()
        cfg_data = json.loads(cfg_file.read_text())
        assert cfg_data["prd_text"] == prd_sample.strip()

def test_playwright_controller_lifecycle():
    controller = PlaywrightController(headless=True)
    try:
        controller.start()
    except Exception as e:
        if "Permission denied" in str(e) or "Target page, context or browser has been closed" in str(e):
            pytest.skip("Playwright browser subprocess requires unsandboxed Mach port permissions.")
        raise
    assert controller.browser is not None
    assert controller.page is not None

    # Test navigating to data URL (fast, zero external network dependency)
    data_url = "data:text/html,<html><head><title>Test App</title></head><body><h1>Welcome</h1><button id='btn-submit'>Submit</button><input name='query' placeholder='Search...' /></body></html>"
    nav = controller.navigate(data_url)
    assert nav["title"] == "Test App"
    assert nav["status"] == 200

    # Test DOM extraction
    dom_summary = controller.get_dom_summary()
    assert dom_summary["title"] == "Test App"
    dom = dom_summary["dom"]
    assert "Welcome" in dom["headings"]
    assert any(b["text"] == "Submit" for b in dom["buttons"])
    assert any(i["name"] == "query" for i in dom["inputs"])

    # Test clicking button
    click_res = controller.click("#btn-submit")
    assert click_res["success"] is True

    # Test typing in input
    fill_res = controller.fill("input[name='query']", "Playwright Automation")
    assert fill_res["success"] is True

    controller.stop()

def test_playwright_explorer_prompt_construction():
    agent = PlaywrightExplorerAgent()

    # URL only
    cfg_no_prd = ExplorerConfig(
        project_id="p1",
        target_url="https://app.test",
        auth_type="form",
        credentials={"username": "alice"},
        scope_instructions="Test login only",
        workspace_dir="/tmp/dummy",
        run_id="r1",
        prd_text=None,
    )
    prompt_no_prd = agent._build_system_prompt(cfg_no_prd, has_prd=False)
    assert "AUTONOMOUS QA EXPLORATORY TOURS" in prompt_no_prd
    assert "https://app.test" in prompt_no_prd

    # URL + PRD
    cfg_with_prd = ExplorerConfig(
        project_id="p2",
        target_url="https://app.test",
        auth_type="none",
        credentials={},
        scope_instructions=None,
        workspace_dir="/tmp/dummy",
        run_id="r2",
        prd_text="Requirement: User must see confirmation modal before deleting.",
    )
    prompt_with_prd = agent._build_system_prompt(cfg_with_prd, has_prd=True)
    assert "SPECIFICATION-DRIVEN EXPLORATORY TESTING" in prompt_with_prd
    assert "User must see confirmation modal before deleting" in prompt_with_prd

def test_playwright_explorer_qa_scenario_structure():
    agent = PlaywrightExplorerAgent()
    assert not hasattr(agent, "_generate_spec_script")

    scenario = DiscoveredScenario(
        title="User Checkout Happy Path",
        category="happy_path",
        priority="P0",
        preconditions="User is logged in with active cart containing 1 item",
        description="User completes checkout with valid credit card",
        steps=[{"step_number": 1, "action": "Click checkout", "target_element": "#checkout-btn", "expected_outcome": "Payment modal opens"}],
        expected_result="Order confirmation number displayed with success message",
        pass_fail_criteria="1. HTTP 200 on /api/orders\n2. Order ID matches format #ORD-[0-9]+\n3. Cart badge counter reset to 0",
    )

    s_dict = scenario.to_dict()
    assert s_dict["priority"] == "P0"
    assert s_dict["preconditions"] == "User is logged in with active cart containing 1 item"
    assert "Pass / Fail Criteria" not in s_dict or s_dict["pass_fail_criteria"] is not None
    assert s_dict["pass_fail_criteria"].startswith("1. HTTP 200")
    assert s_dict["status"] == "pending_review"
    assert s_dict["source"] == "llm"
    assert "suggested_spec_filename" not in s_dict

def test_playwright_explorer_fallback_scenario_tagging():
    agent = PlaywrightExplorerAgent()
    cfg = ExplorerConfig(
        project_id="p-fallback",
        target_url="http://localhost:3000",
        auth_type="none",
        credentials={},
        scope_instructions=None,
        workspace_dir="/tmp/test",
        run_id="run-fallback",
    )
    res = agent._synthesize_spec_only_plan(cfg, lambda lvl, msg, meta=None: None)
    assert len(res.scenarios) > 0
    for sc in res.scenarios:
        assert sc.source == "fallback_template"
        assert sc.description.startswith("⚠️ FALLBACK TEMPLATE")
        assert sc.to_dict()["source"] == "fallback_template"

def test_headless_and_slow_mo_configuration():
    # 1. Test PlaywrightController init options
    ctrl = PlaywrightController(headless=False, slow_mo=500)
    assert ctrl.headless is False
    assert ctrl.slow_mo == 500

    # 2. Test ExplorerConfig fields
    cfg = ExplorerConfig(
        project_id="test-p",
        target_url="http://localhost:3000",
        auth_type="none",
        credentials={},
        scope_instructions=None,
        workspace_dir="/tmp/test",
        run_id="run-1",
        headless=False,
        slow_mo=500,
    )
    assert cfg.headless is False
    assert cfg.slow_mo == 500

    # 3. Test TestRunner init options
    from app.core.test_runner import TestRunner
    runner = TestRunner(
        workspace_dir="/tmp/test",
        project_id="test-p",
        run_id="run-1",
        headless=False,
        slow_mo=750,
    )
    assert runner.headless is False
    assert runner.slow_mo == 750

    # Test default slow_mo fallback for headed mode
    runner_default_slowmo = TestRunner(
        workspace_dir="/tmp/test",
        project_id="test-p",
        run_id="run-1",
        headless=False,
        slow_mo=0,
    )
    assert runner_default_slowmo.headless is False
    assert runner_default_slowmo.slow_mo == 500


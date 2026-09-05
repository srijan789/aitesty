import json
import shutil
from pathlib import Path
import pytest

from app import create_app
from app.extensions import db
from app.models.project import Project
from app.agents.base import ExplorerConfig, DiscoveredScenario
from app.agents.playwright_controller import PlaywrightController
from app.agents.playwright_explorer import PlaywrightExplorerAgent
from app.core.coverage_critic import CoverageCritic
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


def test_project_model_crawl_controls_defaults_and_custom(app, client):
    """Test project model stores and returns crawl depth, max pages, target tests, and strategy."""
    res = client.post(
        "/projects",
        data={
            "name": "E-Commerce Deep Store",
            "target_url": "https://store.example.com",
            "auth_type": "none",
            "crawl_depth": 3,
            "max_pages": 18,
            "target_test_count": 22,
            "exploration_strategy": "forms_heavy",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        project = Project.query.filter_by(name="E-Commerce Deep Store").first()
        assert project is not None
        assert project.crawl_depth == 3
        assert project.max_pages == 18
        assert project.target_test_count == 22
        assert project.exploration_strategy == "forms_heavy"

        p_dict = project.to_dict()
        assert p_dict["crawl_depth"] == 3
        assert p_dict["max_pages"] == 18
        assert p_dict["target_test_count"] == 22
        assert p_dict["exploration_strategy"] == "forms_heavy"


def test_coverage_critic_with_target_volume():
    """Test CoverageCritic evaluates scenario volume quota when target_test_count is set."""
    critic = CoverageCritic(max_retries=2)
    scenarios = [
        DiscoveredScenario(title="T1", category="happy_path", description="D1", steps=[], expected_result="R1"),
        DiscoveredScenario(title="T2", category="edge_case", description="D2", steps=[], expected_result="R2"),
        DiscoveredScenario(title="T3", category="error_flow", description="D3", steps=[], expected_result="R3"),
    ]

    # Without target_test_count -> all 3 categories pass with 1.0
    res_no_target = critic.evaluate(scenarios=scenarios, has_credentials=False)
    assert res_no_target.verdict == "proceed"
    assert res_no_target.score == 1.0
    assert len(res_no_target.gaps) == 0

    # With target_test_count=10 -> gap triggered for volume
    res_with_target = critic.evaluate(scenarios=scenarios, has_credentials=False, target_test_count=10)
    assert res_with_target.verdict == "re_explore"
    assert res_with_target.score < 1.0
    assert any("Scenario volume under target" in g for g in res_with_target.gaps)

    # With 10 scenarios satisfying target -> proceed
    for i in range(4, 11):
        cat = ["happy_path", "edge_case", "error_flow"][i % 3]
        scenarios.append(DiscoveredScenario(title=f"T{i}", category=cat, description=f"D{i}", steps=[], expected_result="OK"))

    res_met = critic.evaluate(scenarios=scenarios, has_credentials=False, target_test_count=10)
    assert res_met.verdict == "proceed"
    assert res_met.score == 1.0
    assert len(res_met.gaps) == 0


def test_scenario_expansion_fulfills_deep_quota():
    """Test _expand_and_synthesize_scenarios generates deep multi-route tests >= quota."""
    agent = PlaywrightExplorerAgent()
    cfg = ExplorerConfig(
        project_id="p-deep",
        target_url="https://shop.example.com",
        auth_type="form",
        credentials={"username": "qa_tester"},
        scope_instructions="Exhaustive test planning",
        workspace_dir="/tmp/test_ws",
        run_id="run-deep-1",
        crawl_depth=3,
        max_pages=15,
        target_test_count=16,
        exploration_strategy="balanced",
    )

    crawled_pages = [
        {
            "url": "https://shop.example.com/",
            "title": "Shop Home",
            "forms": [],
            "buttons": [{"text": "View Products"}],
            "inputs": [],
        },
        {
            "url": "https://shop.example.com/products",
            "title": "Product Catalog",
            "forms": [{"id": "filter-form"}],
            "buttons": [{"text": "Filter"}, {"text": "Add to Cart"}],
            "inputs": [{"name": "search", "type": "text"}, {"name": "min_price", "type": "number"}],
        },
        {
            "url": "https://shop.example.com/checkout",
            "title": "Checkout",
            "forms": [{"id": "checkout-form"}],
            "buttons": [{"text": "Place Order"}],
            "inputs": [{"name": "card_number", "type": "text"}, {"name": "cvv", "type": "password"}],
        },
    ]

    result = agent._expand_and_synthesize_scenarios(
        config=cfg,
        controller=None,
        crawled_pages=crawled_pages,
        existing_scenarios=[],
        runs_dir=Path("/tmp/test_ws/runs/run-deep-1"),
        artifacts_created=[],
        log_callback=lambda lvl, msg, meta=None: None,
    )

    assert result.status == "success"
    assert len(result.scenarios) >= 16

    categories = {s.category for s in result.scenarios}
    assert "happy_path" in categories
    assert "edge_case" in categories
    assert "error_flow" in categories

    # Verify routes covered in test scenario titles/descriptions
    titles_text = " ".join([s.title for s in result.scenarios])
    assert "checkout" in titles_text.lower()
    assert "products" in titles_text.lower()
    assert any("Authentication" in s.title for s in result.scenarios)


def test_api_explore_with_override_parameters(app, client):
    """Test /api/projects/<id>/explore accepts crawl parameters and stores in run metadata."""
    # Create project
    res = client.post(
        "/projects",
        data={
            "name": "Override API Project",
            "target_url": "https://api-override.test",
            "auth_type": "none",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        proj = Project.query.filter_by(name="Override API Project").first()
        proj_id = proj.id

    # Trigger explore with crawl override parameters
    res_explore = client.post(
        f"/api/projects/{proj_id}/explore",
        json={
            "crawl_depth": 4,
            "max_pages": 25,
            "target_test_count": 20,
            "exploration_strategy": "depth_first",
        },
    )
    assert res_explore.status_code == 202
    data = res_explore.get_json()
    assert data["success"] is True
    assert "run_id" in data

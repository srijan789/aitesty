import json
import pytest
from unittest.mock import MagicMock

from app.core.coverage_critic import CoverageCritic, CriticResult
from app.agents.base import DiscoveredScenario, ExplorerResult


def test_coverage_critic_all_categories_satisfied():
    critic = CoverageCritic(max_retries=2)
    scenarios = [
        DiscoveredScenario(
            title="Checkout Happy Path",
            category="happy_path",
            priority="P0",
            description="User completes purchase",
            steps=[],
            expected_result="Order placed",
        ),
        DiscoveredScenario(
            title="Max Length Input",
            category="edge_case",
            priority="P1",
            description="Submit 500 character string",
            steps=[],
            expected_result="Field truncated or validated",
        ),
        DiscoveredScenario(
            title="404 Page Verification",
            category="error_flow",
            priority="P1",
            description="Navigating to non-existent route shows error",
            steps=[],
            expected_result="Error message displayed",
        ),
    ]

    res = critic.evaluate(scenarios=scenarios, has_credentials=False, retry_count=0)
    assert res.verdict == "proceed"
    assert res.score == 1.0
    assert len(res.gaps) == 0
    assert "Coverage standards met" in res.feedback
    assert res.counts["happy_path"] == 1
    assert res.counts["edge_case"] == 1
    assert res.counts["error_flow"] == 1


def test_coverage_critic_gap_triggers_re_explore():
    critic = CoverageCritic(max_retries=2)
    # Only happy_path scenario, missing edge_case and error_flow
    scenarios = [
        DiscoveredScenario(
            title="Home Page Load",
            category="happy_path",
            priority="P0",
            description="Page renders",
            steps=[],
            expected_result="HTTP 200",
        ),
    ]

    # Attempt 0: Should return re_explore with 2 gaps
    res = critic.evaluate(scenarios=scenarios, has_credentials=False, retry_count=0)
    assert res.verdict == "re_explore"
    assert res.score < 1.0
    assert len(res.gaps) == 2
    assert any("edge case" in g.lower() for g in res.gaps)
    assert any("error flow" in g.lower() for g in res.gaps)
    assert "Directives for re-exploration" in res.feedback

    # Attempt 1: Still has gaps, retry_count=1 < 2 -> re_explore
    res1 = critic.evaluate(scenarios=scenarios, has_credentials=False, retry_count=1)
    assert res1.verdict == "re_explore"


def test_coverage_critic_escalates_after_max_retries():
    critic = CoverageCritic(max_retries=2)
    # Only happy_path scenario on single static page
    scenarios = [
        DiscoveredScenario(
            title="Single Static Page View",
            category="happy_path",
            priority="P0",
            description="Static page loads",
            steps=[],
            expected_result="HTTP 200",
        ),
    ]

    # When retry_count reaches max_retries (2), should honestly escalate
    res = critic.evaluate(scenarios=scenarios, has_credentials=False, retry_count=2)
    assert res.verdict == "escalate"
    assert "Escalating for human review without hallucinating synthetic scenarios" in res.feedback
    assert len(res.gaps) > 0


def test_coverage_critic_auth_requirement_when_credentials_present():
    critic = CoverageCritic(max_retries=2)
    scenarios = [
        DiscoveredScenario(title="View Dashboard", category="happy_path", description="Dashboard view", steps=[], expected_result="OK"),
        DiscoveredScenario(title="Boundary Input", category="edge_case", description="Long string", steps=[], expected_result="OK"),
        DiscoveredScenario(title="Error Route", category="error_flow", description="404 check", steps=[], expected_result="OK"),
    ]

    # When has_credentials=True, but no scenarios mention auth/login
    res_no_auth = critic.evaluate(scenarios=scenarios, has_credentials=True, retry_count=0)
    assert res_no_auth.verdict == "re_explore"
    assert any("authentication" in g.lower() for g in res_no_auth.gaps)
    assert res_no_auth.score == 0.75  # 3 of 4 criteria met

    # Now add an authentication scenario
    auth_scenario = DiscoveredScenario(
        title="User Login Flow",
        category="happy_path",
        description="Verify user can sign in with valid credentials",
        steps=[{"step_number": 1, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": "Credentials entered"}],
        expected_result="User session established",
    )
    scenarios.append(auth_scenario)

    res_with_auth = critic.evaluate(scenarios=scenarios, has_credentials=True, retry_count=0)
    assert res_with_auth.verdict == "proceed"
    assert res_with_auth.score == 1.0
    assert len(res_with_auth.gaps) == 0


def test_coverage_critic_to_dict_serialization():
    critic = CoverageCritic(max_retries=2)
    res = critic.evaluate(scenarios=[], has_credentials=False, retry_count=1)
    d = res.to_dict()
    assert d["verdict"] == "re_explore"
    assert "score" in d
    assert "gaps" in d
    assert "feedback" in d
    assert "counts" in d
    assert d["retry_count"] == 1

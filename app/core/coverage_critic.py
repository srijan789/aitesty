import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.agents.base import DiscoveredScenario

logger = logging.getLogger(__name__)


@dataclass
class CriticResult:
    """Diagnostic evaluation result returned by CoverageCritic."""
    verdict: str  # "proceed" | "re_explore" | "escalate"
    score: float  # 0.0 to 1.0
    gaps: List[str] = field(default_factory=list)
    feedback: str = ""
    counts: Dict[str, int] = field(default_factory=dict)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "gaps": self.gaps,
            "feedback": self.feedback,
            "counts": self.counts,
            "retry_count": self.retry_count,
        }


class CoverageCritic:
    """
    Evaluates discovered QA test scenarios against coverage standards.
    Scores category distributions (happy_path, edge_case, error_flow) and
    verifies authentication coverage when credentials are configured.
    Decides whether to proceed, re-explore with targeted feedback, or escalate.
    """

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def evaluate(
        self,
        scenarios: List[DiscoveredScenario],
        has_credentials: bool = False,
        retry_count: int = 0,
        target_test_count: Optional[int] = None,
        discovered_routes: Optional[List[str]] = None,
    ) -> CriticResult:
        """
        Analyzes scenarios, tallies category counts, checks auth coverage,
        verifies target scenario volume (if requested), and returns a CriticResult.
        """
        happy_count = sum(1 for s in scenarios if getattr(s, "category", "") == "happy_path")
        edge_count = sum(1 for s in scenarios if getattr(s, "category", "") == "edge_case")
        error_count = sum(1 for s in scenarios if getattr(s, "category", "") == "error_flow")

        # Check authentication coverage
        auth_keywords = ["login", "sign in", "signin", "auth", "credential", "session", "logout"]
        auth_count = 0
        for s in scenarios:
            text_corpus = (
                f"{getattr(s, 'title', '')} {getattr(s, 'description', '')} "
                f"{getattr(s, 'preconditions', '')} {getattr(s, 'expected_result', '')}"
            ).lower()
            steps = getattr(s, "steps", [])
            for st in steps:
                if isinstance(st, dict):
                    text_corpus += f" {st.get('action', '')} {st.get('target_element', '')} {st.get('expected_outcome', '')}".lower()
                else:
                    text_corpus += f" {str(st)}".lower()

            if any(kw in text_corpus for kw in auth_keywords):
                auth_count += 1

        counts = {
            "total": len(scenarios),
            "happy_path": happy_count,
            "edge_case": edge_count,
            "error_flow": error_count,
            "auth_coverage": auth_count,
        }
        if target_test_count is not None:
            counts["target_test_count"] = target_test_count

        gaps: List[str] = []
        guidance: List[str] = []

        total_criteria = 3  # happy, edge, error
        satisfied_criteria = 0

        # Category checks
        if happy_count > 0:
            satisfied_criteria += 1
        else:
            gaps.append("Missing happy path coverage (no core workflows discovered)")
            guidance.append("Explore core functional journeys, primary views, navigation menus, and standard user interactions.")

        if edge_count > 0:
            satisfied_criteria += 1
        else:
            gaps.append("Missing edge case coverage (no boundary inputs or edge conditions tested)")
            guidance.append("Probe input fields with boundary lengths, empty inputs, special characters, or extreme state transitions.")

        if error_count > 0:
            satisfied_criteria += 1
        else:
            gaps.append("Missing error flow coverage (no invalid inputs or error handling tested)")
            guidance.append("Test invalid routes, invalid form data, and check for appropriate error messages or 404 responses.")

        # Scenario Volume Check (only if specified)
        if target_test_count is not None and target_test_count > 0:
            total_criteria += 1
            if len(scenarios) >= target_test_count:
                satisfied_criteria += 1
            else:
                gaps.append(f"Scenario volume under target ({len(scenarios)} generated vs {target_test_count} target)")
                guidance.append(f"Expand testing breadth across routes and forms to reach at least {target_test_count} comprehensive scenarios.")

        # Auth check
        if has_credentials:
            total_criteria += 1
            if auth_count > 0:
                satisfied_criteria += 1
            else:
                gaps.append("Missing authentication flow coverage (credentials configured but no auth scenarios discovered)")
                guidance.append("Explore login/sign-in flows using the configured credentials, verifying successful session creation and invalid login handling.")

        score = round(satisfied_criteria / total_criteria, 2) if total_criteria > 0 else 1.0

        # Decision logic: proceed, re_explore, or escalate
        if not gaps:
            verdict = "proceed"
            feedback = "Coverage standards met across all required categories."
        elif retry_count < self.max_retries:
            verdict = "re_explore"
            feedback = f"Coverage gaps detected: {'; '.join(gaps)}. Directives for re-exploration: {' '.join(guidance)}"
        else:
            verdict = "escalate"
            feedback = (
                f"Coverage gaps persist after {retry_count} re-exploration attempts ({'; '.join(gaps)}). "
                f"Escalating for human review without hallucinating synthetic scenarios."
            )

        return CriticResult(
            verdict=verdict,
            score=score,
            gaps=gaps,
            feedback=feedback,
            counts=counts,
            retry_count=retry_count,
        )

import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

REQUIRED_CATEGORIES = ["happy_path", "edge_case", "error_flow"]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "should",
    "must", "is", "are", "be", "this", "that", "it", "as", "by", "from", "at", "user",
    "users", "flow", "flows", "test", "tests", "application", "app",
}


@dataclass
class CoverageReport:
    score: float
    gaps: List[str] = field(default_factory=list)
    missing_categories: List[str] = field(default_factory=list)
    uncovered_routes: List[str] = field(default_factory=list)
    unaddressed_requirements: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "gaps": self.gaps,
            "missing_categories": self.missing_categories,
            "uncovered_routes": self.uncovered_routes,
            "unaddressed_requirements": self.unaddressed_requirements,
        }


def _extract_keywords(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z]{4,}", (text or "").lower())
    return sorted({w for w in words if w not in _STOPWORDS})


class CoverageEvaluator:
    """
    Rule-based evaluation of a test plan's coverage quality, run by the orchestrator between
    the Planning and Generation stages. Deliberately kept as its own class (not a registered
    sub-agent) so it can be swapped for an LLM-based evaluator later without touching the
    orchestrator's control flow.
    """

    def evaluate(
        self,
        plan_dict: Dict[str, Any],
        discovered_routes: Optional[List[str]] = None,
        requirements_text: Optional[str] = None,
    ) -> CoverageReport:
        scenarios = plan_dict.get("scenarios", []) or []
        discovered_routes = discovered_routes or plan_dict.get("discovered_routes", []) or []
        gaps: List[str] = []

        # 1. Category presence
        present_categories = {s.get("category") for s in scenarios}
        missing_categories = [c for c in REQUIRED_CATEGORIES if c not in present_categories]
        for c in missing_categories:
            gaps.append(f"No scenarios cover the '{c}' category.")

        # 2. Route coverage: does at least one scenario step reference each discovered route?
        scenario_targets = set()
        for s in scenarios:
            for step in s.get("steps", []):
                target = (step.get("target_element") or "") if isinstance(step, dict) else ""
                scenario_targets.add(target.lower())
        uncovered_routes = []
        for route in discovered_routes:
            path = route.rstrip("/").split("/")[-1] if route.rstrip("/") else ""
            if not path:
                continue
            if not any(path.lower() in target for target in scenario_targets):
                uncovered_routes.append(route)
        for route in uncovered_routes:
            gaps.append(f"Discovered route '{route}' is not exercised by any scenario.")

        # 3. Requirements/scope keyword coverage
        unaddressed_requirements = []
        if requirements_text:
            keywords = _extract_keywords(requirements_text)
            haystack = " ".join(
                f"{s.get('title', '')} {s.get('description', '')}" for s in scenarios
            ).lower()
            for kw in keywords:
                if kw not in haystack:
                    unaddressed_requirements.append(kw)
            for kw in unaddressed_requirements:
                gaps.append(f"Requirement keyword '{kw}' is not reflected in any scenario.")

        # Score: weighted combination, clamped to [0, 1]
        category_score = 1.0 - (len(missing_categories) / len(REQUIRED_CATEGORIES))
        route_score = 1.0 if not discovered_routes else 1.0 - (len(uncovered_routes) / len(discovered_routes))
        if requirements_text:
            kw_total = len(_extract_keywords(requirements_text)) or 1
            requirement_score = 1.0 - (len(unaddressed_requirements) / kw_total)
            score = round((category_score * 0.4) + (route_score * 0.3) + (requirement_score * 0.3), 3)
        else:
            score = round((category_score * 0.6) + (route_score * 0.4), 3)

        return CoverageReport(
            score=max(0.0, min(1.0, score)),
            gaps=gaps,
            missing_categories=missing_categories,
            uncovered_routes=uncovered_routes,
            unaddressed_requirements=unaddressed_requirements,
        )

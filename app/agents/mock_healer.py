import logging
from typing import Dict, Any, List, Optional, Callable
from app.agents.base import (
    BaseHealingAgent,
    HealingConfig,
    HealingResult,
    FailedCaseAnalysis,
)

logger = logging.getLogger(__name__)

class MockHealingAgent(BaseHealingAgent):
    """
    Mock Test Results Analysis & Healing Agent for lightning-fast, offline deterministic testing.
    """

    def analyze_and_heal(
        self,
        config: HealingConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> HealingResult:
        log_callback("INFO", f"[MockHealer] Initializing Mock Healing Agent for project {config.project_id}")
        log_callback("INFO", f"[MockHealer] Analyzing {len(config.run_ids)} test runs")

        analyses: List[FailedCaseAnalysis] = []
        app_defects = 0
        auto_failures = 0
        healed_count = 0
        invalid_count = 0

        # Create mock analyses for demonstration / testing
        for run_id in config.run_ids:
            a1 = FailedCaseAnalysis(
                test_name="test_login_submit",
                scenario_id="mock-sc-01",
                scenario_title="User Authentication Flow",
                file_name="test_01_auth.spec.py",
                status="failed",
                failure_origin="AUTOMATION_FAILURE",
                verdict="NEEDS_FIX",
                summary="Locator drift: button#submit changed to button[data-testid='login-btn']",
                root_cause="Button selector in login form was modified during frontend release.",
                notes_for_planner="Scenario valid. Script needs locator update to resilient data-testid.",
                notes_for_generator="Replace selector 'button#submit' with \"button[data-testid='login-btn']\" or \"button:has-text('Sign In')\".",
                suggested_fix="Replace broken selector 'button#submit' with resilient alternative: \"button[data-testid='login-btn']\"",
                suggested_selectors=["[data-testid='login-btn']", "button:has-text('Sign In')"],
                confidence=0.95,
                raw_error="TimeoutError: Locator button#submit not found within 8000ms",
            )
            analyses.append(a1)
            auto_failures += 1
            healed_count += 1

            a2 = FailedCaseAnalysis(
                test_name="test_checkout_payment",
                scenario_id="mock-sc-02",
                scenario_title="Payment Gateway Integration",
                file_name="test_02_checkout.spec.py",
                status="failed",
                failure_origin="PRODUCT_DEFECT",
                verdict="REAL_BUG",
                summary="Real Product Defect: Backend returned HTTP 500 Internal Server Error on payment submit.",
                root_cause="Payment processing endpoint crashed with unhandled exception on valid payload.",
                notes_for_planner="CRITICAL DEFECT: Backend payment API returned 500. Scenario is valid and caught a product regression.",
                notes_for_generator="Do not change test assertions. Test correctly detected backend failure.",
                suggested_fix="Escalate bug defect report to product backend team: HTTP 500 on POST /api/checkout/pay",
                suggested_selectors=[],
                confidence=0.98,
                raw_error="AssertionError: Target URL returned HTTP 500",
            )
            analyses.append(a2)
            app_defects += 1

        log_callback(
            "INFO",
            f"[MockHealer] Finished analysis: {len(analyses)} failed cases. Defects: {app_defects}, Auto: {auto_failures}",
        )

        return HealingResult(
            status="success",
            analyzed_runs=config.run_ids,
            failed_cases_analyzed=len(analyses),
            app_defects_count=app_defects,
            automation_failures_count=auto_failures,
            healed_tests_count=healed_count,
            invalid_tests_count=invalid_count,
            analyses=analyses,
        )

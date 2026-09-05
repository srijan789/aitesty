import time
from typing import Dict, Any, Optional, Callable
from app.agents.base import BaseHealerAgent, HealerConfig, HealerResult


class MockHealerAgent(BaseHealerAgent):
    """
    Stage 3 Mock Healer Agent.
    Simulates classifying a test failure as a broken script (stale locator, drifted workflow
    step) vs a genuine application defect. Repairs the script directly for the former; for the
    latter it never touches application code, it only classifies and recommends a fix.
    """

    def heal(
        self,
        config: HealerConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> HealerResult:
        failure = (config.failure_output or "").lower()

        log_callback(
            "INFO",
            f"Healer analyzing failure for test case {config.test_case_id} (attempt {config.attempt_number}/{config.max_attempts})",
            None,
        )
        time.sleep(0.2)
        if cancel_check and cancel_check():
            log_callback("WARN", "Healing cancelled by user request.", None)
            return HealerResult(status="unresolved", classification="unknown", action_taken="escalated", error_message="cancelled")

        # Marker used by tests to simulate a script bug the healer can never actually fix,
        # to exercise the max-attempts exhaustion path.
        if "persistent_bug" in failure:
            log_callback("WARN", "Applied a script repair attempt, but the issue appears to persist.", None)
            return HealerResult(
                status="unresolved",
                classification="script_bug",
                action_taken="repaired_script",
                updated_script_content=f'"""Healer repair attempt {config.attempt_number}"""\nfrom playwright.sync_api import Page\n\ndef test_healed(page: Page):\n    pass\n',
                confidence=0.4,
            )

        if any(keyword in failure for keyword in ("selector", "locator", "timeout")):
            resolved = config.attempt_number >= 2
            log_callback(
                "INFO",
                f"Classified as a broken test script (stale selector/timing). {'Repair verified.' if resolved else 'Repairing and will verify on rerun.'}",
                None,
            )
            return HealerResult(
                status="resolved" if resolved else "unresolved",
                classification="script_bug",
                action_taken="repaired_script",
                updated_script_content=(
                    f'"""Healed by MockHealerAgent (attempt {config.attempt_number})"""\n'
                    f'from playwright.sync_api import Page, expect\n\n'
                    f'def test_healed(page: Page):\n'
                    f'    page.wait_for_selector("body", timeout=5000)\n'
                ),
                confidence=0.8 if resolved else 0.5,
            )

        # Anything else is treated as a suspected genuine application defect. The Healer never
        # modifies application code -- it only classifies and hands back a recommendation.
        log_callback(
            "WARN",
            "Classified as a likely application defect (not a broken locator/workflow) -- recommending a fix for review.",
            None,
        )
        return HealerResult(
            status="escalated",
            classification="app_defect",
            action_taken="recommended_fix",
            recommendation_text=f"Investigate application behavior: {config.failure_output[:300]}",
            confidence=0.6,
        )

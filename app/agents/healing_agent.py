import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from openai import OpenAI
from app.agents.base import (
    BaseHealingAgent,
    HealingConfig,
    HealingResult,
    FailedCaseAnalysis,
)
from app.core.telemetry import classify_failure, FailureClassification, FailureSubType

logger = logging.getLogger(__name__)

HEALING_MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_healing_analysis",
            "description": "Records comprehensive test failure attribution, verdict (needs fix vs invalid testcase vs real bug), and notes for planner and generator agents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_name": {"type": "string", "description": "Name of the test function, e.g. test_login_submit."},
                    "failure_origin": {
                        "type": "string",
                        "enum": ["PRODUCT_DEFECT", "AUTOMATION_FAILURE", "UNKNOWN"],
                        "description": "Attribution: PRODUCT_DEFECT (real app/backend/frontend bug) vs AUTOMATION_FAILURE (selector drift, wait timeout, broken script)."
                    },
                    "verdict": {
                        "type": "string",
                        "enum": ["NEEDS_FIX", "INVALID_TESTCASE", "REAL_BUG"],
                        "description": "Verdict: NEEDS_FIX (script locator/assertion heal), INVALID_TESTCASE (scenario obsolete/impossible/removed), REAL_BUG (application defect report)."
                    },
                    "summary": {"type": "string", "description": "Concise 1-2 sentence diagnosis summary."},
                    "root_cause": {"type": "string", "description": "In-depth root cause explanation."},
                    "notes_for_planner": {
                        "type": "string",
                        "description": "Actionable notes for the test planning agent (whether scenario requires rework, deprecation, or bug tracking)."
                    },
                    "notes_for_generator": {
                        "type": "string",
                        "description": "Precise guidance for the test generator agent (e.g. resilient selectors to use, wait strategy, assertion adjustments)."
                    },
                    "suggested_fix": {"type": "string", "description": "Single line recommended fix for engineers or automation."},
                    "suggested_selectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Alternative resilient selectors found in the DOM (e.g. data-testid, role, text)."
                    },
                    "confidence": {"type": "number", "description": "Confidence score between 0.0 and 1.0."}
                },
                "required": ["test_name", "failure_origin", "verdict", "summary", "root_cause", "notes_for_planner", "notes_for_generator"]
            }
        }
    }
]

class PlaywrightHealingAgent(BaseHealingAgent):
    """
    Autonomous Test Results Analysis & Healing Agent powered by Gemini via TrueFoundry Gateway
    with a deterministic fallback rules engine.
    
    Responsibilities:
    1. Ingests failed test cases and their isolated per-test logs & telemetry.
    2. Identifies failure attribution: Automation Failure vs Product Bug (Real Failure).
    3. Decides whether the testcase needs to be healed (script fix) or is invalid/obsolete.
    4. Produces actionable notes for the Planning Agent and Test Generator Agent.
    5. Syncs healing metadata into TestCase DB models and workspace files.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get(
            "TRUEFOUNDRY_API_KEY",
            "tfy_pat_default-u3n8eaqjipdolz2w8cz3uhcm_0E2iyumk9OfB7Vo68461d1270ac232560fa7cdd084688708",
        )
        self.base_url = base_url or os.environ.get("TRUEFOUNDRY_BASE_URL", "https://gateway.truefoundry.ai")
        self.model = model or os.environ.get("HEALER_MODEL", "openrouter/google-gemini-3.7-flash")

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def analyze_and_heal(
        self,
        config: HealingConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> HealingResult:
        def is_cancelled() -> bool:
            if cancel_check and cancel_check():
                log_callback("WARN", "Healing analysis cancelled by user request.", None)
                return True
            return False

        log_callback("INFO", f"Initializing Test Results Analysis & Healing Agent for project {config.project_id}")
        log_callback("INFO", f"Analyzing runs: {', '.join(config.run_ids)}")

        # Collect failed test cases across all specified runs
        failed_tests_map: Dict[str, Dict[str, Any]] = {}
        workspace_path = Path(config.workspace_dir)

        for run_id in config.run_ids:
            run_dir = workspace_path / "runs" / run_id
            results_path = run_dir / "results.json"
            results_data = {}
            if results_path.exists():
                try:
                    with open(results_path, "r", encoding="utf-8") as f:
                        results_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read results.json from {run_id}: {e}")

            if not results_data and config.run_results:
                results_data = config.run_results[0]

            tests_in_run = results_data.get("tests", [])
            for t in tests_in_run:
                if t.get("status") == "failed":
                    test_name = t.get("test_name", "unnamed_test")
                    # Try reading isolated log file
                    isolated_log = ""
                    test_log_file = run_dir / "test_logs" / f"{test_name}.log"
                    if test_log_file.exists():
                        try:
                            isolated_log = test_log_file.read_text(encoding="utf-8")
                        except Exception:
                            pass
                    
                    failed_tests_map[f"{run_id}:{test_name}"] = {
                        "run_id": run_id,
                        "test_data": t,
                        "isolated_log": isolated_log,
                    }

        if not failed_tests_map:
            log_callback("INFO", "No failed test cases discovered across the selected test runs. Everything is healthy!")
            return HealingResult(
                status="success",
                analyzed_runs=config.run_ids,
                failed_cases_analyzed=0,
                app_defects_count=0,
                automation_failures_count=0,
                healed_tests_count=0,
                invalid_tests_count=0,
                analyses=[],
            )

        log_callback("INFO", f"Identified {len(failed_tests_map)} failed test case execution(s) requiring diagnosis and healing.")

        analyses: List[FailedCaseAnalysis] = []
        app_defects_count = 0
        automation_failures_count = 0
        healed_tests_count = 0
        invalid_tests_count = 0
        artifacts_created: List[str] = []

        client = self._get_client()

        for key, item in failed_tests_map.items():
            if is_cancelled():
                return HealingResult(status="cancelled", analyzed_runs=config.run_ids)

            run_id = item["run_id"]
            test_data = item["test_data"]
            isolated_log = item["isolated_log"]
            test_name = test_data.get("test_name", "unnamed_test")
            scenario_title = test_data.get("scenario_title") or test_data.get("title") or test_name
            scenario_id = test_data.get("scenario_id")

            log_callback("INFO", f"Diagnosing failure in '{test_name}' (Scenario: '{scenario_title}')...")

            # Perform AI or heuristic diagnosis
            analysis = self._diagnose_single_failure(
                client=client,
                config=config,
                test_data=test_data,
                isolated_log=isolated_log,
                log_callback=log_callback,
            )
            analyses.append(analysis)

            if analysis.failure_origin == "PRODUCT_DEFECT":
                app_defects_count += 1
                log_callback("ERROR", f"  [PRODUCT DEFECT] {test_name}: {analysis.summary}")
            else:
                automation_failures_count += 1
                if analysis.verdict == "INVALID_TESTCASE":
                    invalid_tests_count += 1
                    log_callback("WARN", f"  [INVALID TESTCASE] {test_name}: {analysis.summary}")
                else:
                    healed_tests_count += 1
                    log_callback("INFO", f"  [NEEDS FIX / HEALED] {test_name}: {analysis.summary}")

        # Persist healing report into each analyzed run directory
        report_data = {
            "success": True,
            "project_id": config.project_id,
            "target_url": config.target_url,
            "run_id": config.run_ids[0] if config.run_ids else None,
            "analyzed_runs": config.run_ids,
            "failed_cases_analyzed": len(analyses),
            "total_failed": len(analyses),
            "app_defects_count": app_defects_count,
            "automation_failures_count": automation_failures_count,
            "healed_tests_count": healed_tests_count,
            "invalid_tests_count": invalid_tests_count,
            "analyses": [a.to_dict() for a in analyses],
        }

        for run_id in config.run_ids:
            run_dir = workspace_path / "runs" / run_id
            if run_dir.exists():
                rep_file = run_dir / "healing_report.json"
                try:
                    with open(rep_file, "w", encoding="utf-8") as f:
                        json.dump(report_data, f, indent=2)
                    artifacts_created.append(str(rep_file))
                except Exception as e:
                    logger.warning(f"Could not save healing_report.json to {run_dir}: {e}")

        # Update TestCase models in DB and sync to test_plan.json
        self._sync_healing_to_test_plan(config, analyses, log_callback)

        log_callback(
            "INFO",
            f"Healing Analysis Complete: {len(analyses)} failed cases inspected. "
            f"Defects: {app_defects_count}, Automation Failures: {automation_failures_count} "
            f"(Healed: {healed_tests_count}, Invalid/Obsolete: {invalid_tests_count}).",
            report_data,
        )

        return HealingResult(
            status="success",
            analyzed_runs=config.run_ids,
            failed_cases_analyzed=len(analyses),
            app_defects_count=app_defects_count,
            automation_failures_count=automation_failures_count,
            healed_tests_count=healed_tests_count,
            invalid_tests_count=invalid_tests_count,
            analyses=analyses,
            artifacts_created=artifacts_created,
        )

    def _diagnose_single_failure(
        self,
        client: OpenAI,
        config: HealingConfig,
        test_data: Dict[str, Any],
        isolated_log: str,
        log_callback: Callable,
    ) -> FailedCaseAnalysis:
        """Diagnoses a single failed test case using LLM with deterministic heuristic fallback."""
        test_name = test_data.get("test_name", "test")
        scenario_id = test_data.get("scenario_id")
        scenario_title = test_data.get("scenario_title") or test_name
        file_name = test_data.get("file_name")
        error_details = test_data.get("error_details") or {}
        error_message = error_details.get("error_message") or test_data.get("error_message") or "Unknown error"
        traceback_str = error_details.get("traceback") or test_data.get("traceback") or ""
        classification_data = error_details.get("classification") or test_data.get("classification") or {}
        if not classification_data and test_data.get("failure_classification"):
            classification_data = {"classification": test_data.get("failure_classification")}
        steps = test_data.get("steps") or []
        network_events = test_data.get("network_events") or []
        console_messages = test_data.get("console_messages") or []
        candidates = test_data.get("element_candidates") or []

        # Attempt LLM diagnosis
        system_prompt = (
            "You are a Principal QA Architect and AI Test Healing Specialist.\n"
            "Analyze the failed Playwright test case and its execution logs.\n"
            "Your tasks:\n"
            "1. Failure Origin: Distinguish PRODUCT_DEFECT (genuine application outage, 500 backend error, crash, uncaught exception) "
            "from AUTOMATION_FAILURE (locator timeout, changed button text, wait timeout, broken test script).\n"
            "2. Verdict: Decide between:\n"
            "   - 'NEEDS_FIX': The testcase is valid, but the script needs healing (e.g. alternative locator, wait adjustment).\n"
            "   - 'INVALID_TESTCASE': The testcase is obsolete/invalid (e.g. feature removed, 404 dead route, impossible precondition).\n"
            "   - 'REAL_BUG': Genuine product bug that needs escalation to developers.\n"
            "3. Provide notes_for_planner (to update the QA test plan or reject invalid scenarios).\n"
            "4. Provide notes_for_generator (concrete instructions for synthesizing a healed script).\n"
            "Call the record_healing_analysis function with your findings."
        )

        user_prompt = f"""Target Application: {config.target_url}
PRD Context: {config.prd_text or 'Standard Web Application'}
Scope Instructions: {config.scope_instructions or 'None'}

Test Name: {test_name}
Scenario Title: {scenario_title} (ID: {scenario_id})
File: {file_name}
Error Message: {error_message}

Traceback:
{traceback_str[:800]}

Execution Steps:
{json.dumps(steps, indent=2)}

Network Events (last 5):
{json.dumps(network_events[-5:], indent=2)}

Console Messages:
{json.dumps(console_messages[-5:], indent=2)}

Live DOM Candidates:
{json.dumps(candidates[:10], indent=2)}

Isolated Test Log Preview:
{isolated_log[:1000]}
"""

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=HEALING_MCP_TOOLS,
                tool_choice={"type": "function", "function": {"name": "record_healing_analysis"}},
                extra_headers={
                    "X-TFY-METADATA": "{}",
                    "X-TFY-LOGGING-CONFIG": '{"enabled": true}',
                },
            )
            message = response.choices[0].message
            if message.tool_calls:
                args = json.loads(message.tool_calls[0].function.arguments)
                return FailedCaseAnalysis(
                    test_name=test_name,
                    scenario_id=scenario_id,
                    scenario_title=scenario_title,
                    file_name=file_name,
                    status="failed",
                    failure_origin=args.get("failure_origin", "UNKNOWN"),
                    verdict=args.get("verdict", "NEEDS_FIX"),
                    summary=args.get("summary", ""),
                    root_cause=args.get("root_cause", ""),
                    notes_for_planner=args.get("notes_for_planner", ""),
                    notes_for_generator=args.get("notes_for_generator", ""),
                    suggested_fix=args.get("suggested_fix"),
                    suggested_selectors=args.get("suggested_selectors", []),
                    confidence=float(args.get("confidence", 0.9)),
                    raw_error=error_message,
                )
        except Exception as e:
            logger.info(f"LLM healing call fallback triggered: {e}")

        # Deterministic Heuristic Analysis Fallback
        return self._heuristic_diagnosis(
            test_data=test_data,
            error_message=error_message,
            traceback_str=traceback_str,
            classification_data=classification_data,
            candidates=candidates,
            network_events=network_events,
            console_messages=console_messages,
        )

    def _heuristic_diagnosis(
        self,
        test_data: Dict[str, Any],
        error_message: str,
        traceback_str: str,
        classification_data: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        network_events: List[Dict[str, Any]],
        console_messages: List[Dict[str, Any]],
    ) -> FailedCaseAnalysis:
        """Deterministic heuristic diagnosis engine with pattern matching."""
        test_name = test_data.get("test_name", "test")
        scenario_id = test_data.get("scenario_id")
        scenario_title = test_data.get("scenario_title") or test_name
        file_name = test_data.get("file_name")

        err_lower = error_message.lower()
        tb_lower = traceback_str.lower()

        # Check if already classified as App Defect by telemetry
        base_class = classification_data.get("classification") or ""

        # Check for dead route / 404 (Invalid Testcase)
        is_404 = any(isinstance(n, dict) and n.get("status") == 404 for n in network_events) or "404" in err_lower
        if is_404:
            return FailedCaseAnalysis(
                test_name=test_name,
                scenario_id=scenario_id,
                scenario_title=scenario_title,
                file_name=file_name,
                status="failed",
                failure_origin="AUTOMATION_FAILURE",
                verdict="INVALID_TESTCASE",
                summary=f"Route returned HTTP 404 Not Found. Testcase targets obsolete or non-existent endpoint.",
                root_cause="The target URL or navigation path does not exist on the application server.",
                notes_for_planner="Scenario should be marked as Invalid or removed: route returned HTTP 404.",
                notes_for_generator="Do not re-generate test code for this scenario until route path is updated in test plan.",
                suggested_fix="Verify route URL in test plan and either update target URL or reject testcase.",
                suggested_selectors=[],
                confidence=0.95,
                raw_error=error_message,
            )

        # Check for Real Product Bug (500 errors, connection refused, uncaught client crash)
        has_500 = any(isinstance(n, dict) and int(n.get("status", 200)) >= 500 for n in network_events)
        is_server_offline = "connection refused" in err_lower or "err_connection_refused" in err_lower
        has_fatal_js = any("uncaught" in str(c.get("text", "")).lower() for c in console_messages)

        if has_500 or is_server_offline or has_fatal_js or base_class == FailureClassification.APP_DEFECT:
            bug_cause = (
                "Target server is offline or unreachable." if is_server_offline
                else ("Application backend returned HTTP 500 Internal Server Error." if has_500
                else ("Frontend threw an uncaught JavaScript runtime crash." if has_fatal_js
                else "Assertion failure: Application response did not match expected business outcome."))
            )
            return FailedCaseAnalysis(
                test_name=test_name,
                scenario_id=scenario_id,
                scenario_title=scenario_title,
                file_name=file_name,
                status="failed",
                failure_origin="PRODUCT_DEFECT",
                verdict="REAL_BUG",
                summary=f"Real Product Defect: {bug_cause}",
                root_cause=bug_cause,
                notes_for_planner=f"CRITICAL PRODUCT DEFECT: {bug_cause}. Testcase is valid and caught a real regression.",
                notes_for_generator="Do not alter test assertions. Test is correctly validating expected application behavior.",
                suggested_fix=f"Escalate bug defect report to product/engineering team: {bug_cause}",
                suggested_selectors=[],
                confidence=0.92,
                raw_error=error_message,
            )

        # Automation Failure: Locator Drift / Timeout
        alt_selectors = classification_data.get("alternative_selectors") or []
        if not alt_selectors and candidates:
            # Extract candidate selectors from available DOM elements
            for c in candidates[:4]:
                if c.get("testid"):
                    alt_selectors.append(f"[data-testid='{c['testid']}']")
                elif c.get("id"):
                    alt_selectors.append(f"#{c['id']}")
                elif c.get("text"):
                    tag = c.get("tag", "button")
                    alt_selectors.append(f"{tag}:has-text(\"{c['text'][:25]}\")")

        broken_sel = None
        sel_match = re.search(r"['\"]([#.a-zA-Z0-9_\-\[\]=: ]{2,50})['\"]", error_message)
        if sel_match:
            broken_sel = sel_match.group(1)

        suggested_fix = (
            f"Replace broken selector '{broken_sel}' with resilient alternative: '{alt_selectors[0]}'"
            if alt_selectors else "Update locator to use text or aria-role with increased wait timeout."
        )

        return FailedCaseAnalysis(
            test_name=test_name,
            scenario_id=scenario_id,
            scenario_title=scenario_title,
            file_name=file_name,
            status="failed",
            failure_origin="AUTOMATION_FAILURE",
            verdict="NEEDS_FIX",
            summary=f"Locator drift / timeout waiting for element. Automated script needs healing.",
            root_cause=f"The test script failed waiting for selector `{broken_sel or 'target'}` due to DOM change or timing delay.",
            notes_for_planner=f"Scenario remains valid. Script requires healing with updated resilient selector mappings.",
            notes_for_generator=(
                f"Update test function `{test_name}`: Replace `{broken_sel}` with `{alt_selectors[0] if alt_selectors else 'resilient locator'}`. "
                "Ensure page is in domcontentloaded state before interaction."
            ),
            suggested_fix=suggested_fix,
            suggested_selectors=alt_selectors[:5],
            confidence=0.88,
            raw_error=error_message,
        )

    def _sync_healing_to_test_plan(
        self,
        config: HealingConfig,
        analyses: List[FailedCaseAnalysis],
        log_callback: Callable,
    ):
        """Updates TestCase models in SQLite DB and synchronizes test_plan.json on disk."""
        from app.extensions import db
        from app.models.test_plan import TestPlan, TestCase
        from app.core.workspace import WorkspaceManager

        try:
            active_plan = TestPlan.query.filter_by(project_id=config.project_id, status="active").first()
            if not active_plan:
                return

            wm = WorkspaceManager(Path(config.workspace_dir).parent)

            for a in analyses:
                # Find matching TestCase by scenario_id or scenario_title
                tc = None
                if a.scenario_id:
                    tc = db.session.get(TestCase, a.scenario_id)
                if not tc and a.scenario_title:
                    tc = TestCase.query.filter_by(test_plan_id=active_plan.id, title=a.scenario_title).first()
                if not tc:
                    # Try matching by title prefix or tokens from test_name or scenario_title
                    title_tokens = [tok for tok in a.scenario_title.split() if len(tok) > 3]
                    clean_tokens = [tok for tok in a.test_name.replace("test_", "").split("_") if len(tok) > 3]
                    search_tokens = title_tokens + clean_tokens
                    for candidate in active_plan.test_cases:
                        if any(tok.lower() in candidate.title.lower() for tok in search_tokens):
                            tc = candidate
                            break

                if tc:
                    a.scenario_id = tc.id
                    # Construct rich healing note
                    origin_tag = f"[{a.failure_origin}]"
                    verdict_tag = f"[{a.verdict}]"
                    note_lines = [
                        f"{origin_tag} {verdict_tag}: {a.summary}",
                        f"Root Cause: {a.root_cause}",
                        f"Notes for Planner: {a.notes_for_planner}",
                        f"Notes for Generator: {a.notes_for_generator}",
                    ]
                    if a.suggested_fix:
                        note_lines.append(f"Suggested Fix: {a.suggested_fix}")
                    if a.suggested_selectors:
                        note_lines.append(f"Alternative Selectors: {', '.join(a.suggested_selectors)}")

                    tc.healing_notes = "\n\n".join(note_lines)

                    if a.failure_origin == "PRODUCT_DEFECT":
                        tc.healing_status = "app_defect"
                    elif a.verdict == "INVALID_TESTCASE":
                        tc.healing_status = "invalid_scenario"
                        tc.status = "rejected"  # Mark invalid so planner / generator knows
                    elif a.verdict == "NEEDS_FIX":
                        tc.healing_status = "needs_script_fix"
                        tc.status = "marked_for_automation"  # Mark for generator agent to re-synthesize!

            db.session.commit()

            # Sync to test_plan.json on disk
            wm.save_test_plan(config.project_id, active_plan.to_dict())
            log_callback("INFO", "Successfully synchronized healing notes and scenario statuses into Test Plan and workspace.")
        except Exception as e:
            logger.warning(f"Error syncing healing notes to Test Plan: {e}")

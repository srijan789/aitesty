import os
import sys
import subprocess
import re
import ast
import time
import json
import logging
import traceback
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from app.core.telemetry import classify_failure, FailureClassification, FailureSubType, TestTelemetryLogger
from app.core.report_generator import save_run_report

logger = logging.getLogger(__name__)

class TestRunner:
    """
    Executes Playwright test suites and individual spec files.
    Performs real target health checks and real Playwright/HTTP execution.
    Instruments execution with diagnostic telemetry to distinguish
    Application Defects (server offline, 500 errors, assertion bugs)
    from Automation Failures (locator drift/timeouts).
    Generates standalone visual HTML & JSON reports for each run.
    """
    __test__ = False

    def __init__(
        self,
        workspace_dir: str,
        project_id: str,
        run_id: str,
        target_url: str = "",
        headless: bool = True,
        slow_mo: int = 0,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.project_id = project_id
        self.run_id = run_id
        self.target_url = target_url
        self.headless = headless
        self.slow_mo = slow_mo if (slow_mo > 0 or headless) else 500
        self.tests_dir = self.workspace_dir / "tests"
        self.runs_dir = self.workspace_dir / "runs" / run_id
        self.screenshots_dir = self.runs_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.test_logs_dir = self.runs_dir / "test_logs"
        self.test_logs_dir.mkdir(parents=True, exist_ok=True)

    def discover_test_files(
        self,
        target_file: Optional[str] = None,
        target_files: Optional[List[str]] = None,
    ) -> List[Path]:
        """Finds spec files to run, either all, specific target file, or a list of target files."""
        if not self.tests_dir.exists():
            return []

        if target_files:
            found = []
            for tf in target_files:
                safe_rel = tf.lstrip("/").replace("../", "")
                p1 = self.workspace_dir / safe_rel
                p2 = self.tests_dir / Path(tf).name
                if p1.exists() and p1.is_file():
                    found.append(p1)
                elif p2.exists() and p2.is_file():
                    found.append(p2)
            return sorted(list(set(found)))

        if target_file:
            safe_rel = target_file.lstrip("/").replace("../", "")
            specific = self.workspace_dir / safe_rel
            if specific.exists() and specific.is_file():
                return [specific]
            direct = self.tests_dir / Path(target_file).name
            if direct.exists() and direct.is_file():
                return [direct]
            return []

        return sorted(list(self.tests_dir.glob("*.py")))

    def extract_test_functions_from_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parses python AST to extract explicit test_ functions, docstrings, and subtests."""
        test_cases = []
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    docstring = ast.get_docstring(node) or ""
                    
                    scenario_id = None
                    category = "happy_path"
                    scenario_title = None
                    subtest_title = node.name.replace("test_", "").replace("_", " ").title()

                    for line in docstring.split("\n"):
                        clean_line = line.strip()
                        if "Scenario ID:" in clean_line:
                            scenario_id = clean_line.split("Scenario ID:")[-1].strip()
                        elif "Scenario:" in clean_line:
                            scenario_title = clean_line.split("Scenario:")[-1].strip()
                        elif "Subtest:" in clean_line:
                            subtest_title = clean_line.split("Subtest:")[-1].strip()
                        elif "Category:" in clean_line:
                            category = clean_line.split("Category:")[-1].strip()

                    test_cases.append({
                        "name": node.name,
                        "title": subtest_title or node.name,
                        "scenario_title": scenario_title or file_path.stem.replace("test_", "").replace("_", " ").title(),
                        "docstring": docstring,
                        "scenario_id": scenario_id,
                        "category": category,
                        "file_path": str(file_path),
                        "file_name": file_path.name,
                    })
        except Exception as e:
            logger.warning(f"Failed to parse test functions from {file_path.name}: {e}")
        return test_cases

    def execute(
        self,
        target_file: Optional[str] = None,
        target_test_name: Optional[str] = None,
        target_files: Optional[List[str]] = None,
        target_test_names: Optional[List[str]] = None,
        log_callback: Optional[Callable[[str, str, Optional[Dict[str, Any]]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Executes test suite or selected tests with real-time log streaming,
        target connectivity check, failure classification, and HTML report compilation.
        """
        start_time = datetime.utcnow()
        cb = log_callback or (lambda lvl, msg, meta=None: None)
        cb("INFO", f"Initializing Test Runner execution for project {self.project_id}")

        files_to_run = self.discover_test_files(target_file=target_file, target_files=target_files)
        if not files_to_run:
            cb("WARN", f"No test specification files found matching target criteria.")
            empty_summary = {
                "total": 0, "passed": 0, "failed": 0, "skipped": 0,
                "duration_ms": 0, "app_defects": 0, "automation_failures": 0,
                "scenarios_count": 0, "subtests_total": 0,
            }
            results = {"summary": empty_summary, "tests": []}
            return results

        cb("INFO", f"Identified {len(files_to_run)} test specification file(s) for execution.")

        # Real Target Health & Connectivity Check
        server_alive = True
        server_error_msg = ""
        if self.target_url:
            try:
                cb("INFO", f"Pre-flight probe: Verifying connectivity to target application at {self.target_url}...")
                resp = requests.get(self.target_url, timeout=4.0, allow_redirects=True)
                cb("INFO", f"Target application online! Responded with HTTP {resp.status_code}")
                if resp.status_code >= 500:
                    server_alive = False
                    server_error_msg = f"Target application backend returned HTTP {resp.status_code} Internal Server Error"
                    cb("ERROR", f"CRITICAL APPLICATION DEFECT: {server_error_msg}")
            except Exception as conn_err:
                server_alive = False
                server_error_msg = f"Target application server is offline or unreachable ({conn_err})"
                cb("ERROR", f"CRITICAL FAILURE: {server_error_msg}")

        all_results: List[Dict[str, Any]] = []
        passed_count = 0
        failed_count = 0
        app_defects_count = 0
        auto_failures_count = 0
        discovered_scenarios = set()

        for file_path in files_to_run:
            if cancel_check and cancel_check():
                cb("WARN", "Test run cancelled during execution.")
                break

            cb("INFO", f"--- Loading Test Suite File: {file_path.name} ---")
            tests_in_file = self.extract_test_functions_from_file(file_path)

            if not tests_in_file:
                tests_in_file = [{
                    "name": file_path.stem,
                    "title": file_path.stem.replace("test_", "").replace("_", " ").title(),
                    "scenario_title": file_path.stem.replace("test_", "").replace("_", " ").title(),
                    "docstring": f"Execution of {file_path.name}",
                    "scenario_id": None,
                    "category": "suite",
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                }]

            for t_info in tests_in_file:
                t_name = t_info["name"]
                if target_test_name and target_test_name not in t_name:
                    continue
                if target_test_names and not any(tt in t_name for tt in target_test_names):
                    continue

                if cancel_check and cancel_check():
                    cb("WARN", "Test run cancelled by user request.")
                    break

                sc_title = t_info.get("scenario_title") or file_path.stem
                discovered_scenarios.add(sc_title)
                cb("INFO", f"▶ Running subtest: {t_name} (Scenario: '{sc_title}') [{t_info.get('category', 'test')}]")
                
                t_result = self._run_single_test_case(
                    file_path=file_path,
                    test_info=t_info,
                    server_alive=server_alive,
                    server_error_msg=server_error_msg,
                    log_callback=cb,
                )

                all_results.append(t_result)
                if t_result["status"] == "passed":
                    passed_count += 1
                    cb("INFO", f"  ✔ {t_name}: PASSED ({t_result['duration_ms']}ms)")
                else:
                    failed_count += 1
                    err_info = t_result.get("error_details", {})
                    classification = err_info.get("classification", {}).get("classification", "UNKNOWN")
                    if classification == FailureClassification.APP_DEFECT:
                        app_defects_count += 1
                        cb("ERROR", f"  ✖ {t_name}: FAILED (APP DEFECT) - {err_info.get('error_message')}")
                    elif classification == FailureClassification.AUTOMATION_FAILURE:
                        auto_failures_count += 1
                        cb("WARN", f"  ✖ {t_name}: FAILED (AUTOMATION FAILURE) - {err_info.get('error_message')}")
                    else:
                        cb("ERROR", f"  ✖ {t_name}: FAILED - {err_info.get('error_message')}")

        tests_breakdown = {}
        for res in all_results:
            fname = res.get("file_name") or "test_suite.spec.py"
            if fname not in tests_breakdown:
                tests_breakdown[fname] = {
                    "file_name": fname,
                    "subtests_total": 0,
                    "passed": 0,
                    "failed": 0,
                    "subtests": [],
                }
            tests_breakdown[fname]["subtests_total"] += 1
            if res.get("status") == "passed":
                tests_breakdown[fname]["passed"] += 1
            else:
                tests_breakdown[fname]["failed"] += 1
            tests_breakdown[fname]["subtests"].append({
                "test_name": res.get("test_name"),
                "title": res.get("title") or res.get("subtest_title"),
                "status": res.get("status"),
            })

        total_duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        summary = {
            "total": len(all_results),
            "subtests_total": len(all_results),
            "scenarios_count": len(discovered_scenarios),
            "tests_count": len(tests_breakdown),
            "passed": passed_count,
            "failed": failed_count,
            "skipped": 0,
            "duration_ms": total_duration_ms,
            "app_defects": app_defects_count,
            "automation_failures": auto_failures_count,
            "subtests_per_test": list(tests_breakdown.values()),
        }

        full_results = {
            "project_id": self.project_id,
            "run_id": self.run_id,
            "target_url": self.target_url,
            "summary": summary,
            "tests": all_results,
            "timestamp": datetime.utcnow().isoformat(),
        }

        cb("INFO", f"Execution finished. {len(discovered_scenarios)} Scenarios ({len(all_results)} Subtests): Passed: {passed_count}, Failed: {failed_count} (Defects: {app_defects_count}, Script: {auto_failures_count}) in {total_duration_ms}ms")

        # Compile and persist results.json and report.html
        try:
            self._save_reports(full_results, cb)
        except Exception as e:
            logger.warning(f"Error while generating HTML test report: {e}")

        return full_results

    def _run_single_test_case(
        self,
        file_path: Path,
        test_info: Dict[str, Any],
        server_alive: bool,
        server_error_msg: str,
        log_callback: Callable,
    ) -> Dict[str, Any]:
        """
        Executes a single test case with real target interaction & telemetry.
        If the server is offline, immediately fails with APP_DEFECT.
        """
        test_name = test_info["name"]
        scenario_id = test_info.get("scenario_id")
        telemetry = TestTelemetryLogger(test_name=test_name, scenario_id=scenario_id)

        def test_cb(level: str, msg: str, meta: Optional[Dict[str, Any]] = None):
            m = dict(meta or {})
            m["test_name"] = test_name
            m["scenario_id"] = scenario_id
            log_callback(level, msg, m)

        # 1. Immediate failure if target server is offline
        if not server_alive:
            test_cb("ERROR", f"    [FAIL] Cannot execute {test_name}: {server_error_msg}")
            telemetry.log_step(
                step_number=1,
                action="Navigate",
                target=self.target_url,
                outcome=f"Connection Refused: {server_error_msg}",
                duration_ms=50,
            )
            classification = classify_failure(
                error_message=server_error_msg,
                traceback_str=f"requests.exceptions.ConnectionError: {server_error_msg}",
                page_url=self.target_url,
            )
            telemetry.mark_failed(
                error_message=server_error_msg,
                traceback_str=f"ConnectionRefused: {server_error_msg}",
                screenshot_path=None,
                classification_data=classification,
            )
            out = telemetry.to_dict()
            out["file_name"] = file_path.name
            out["file_path"] = str(file_path)
            out["title"] = test_info.get("title") or test_name
            out["scenario_title"] = test_info.get("scenario_title")
            out["category"] = test_info.get("category", "functional")
            self._write_test_log_file(out)
            return out

        # 2. Server is online: Execute real pytest against the specific generated file/test
        test_spec = f"{file_path}::{test_name}" if test_name and test_name.startswith("test_") else str(file_path)
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            test_spec,
            "--import-mode=importlib",
            "-s",
        ]
        if not self.headless:
            cmd.append("--headed")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.workspace_dir) + (os.pathsep + env.get("PYTHONPATH", ""))
        if self.target_url:
            env["BASE_URL"] = self.target_url
            env["TARGET_URL"] = self.target_url

        t0 = time.time()
        try:
            test_cb("INFO", f"    [Subprocess] Running pytest {test_spec} (--import-mode=importlib)...")
            proc = subprocess.run(
                cmd,
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            dur = int((time.time() - t0) * 1000)
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            full_output = (stdout + "\n" + stderr).strip()

            # Parse step breadcrumbs from output: [STEP <num>] <action>
            step_lines = [l.strip() for l in stdout.splitlines() if "[STEP " in l or "# Step" in l]
            for idx, st in enumerate(step_lines, 1):
                match = re.search(r'\[STEP\s*(\d+)\]\s*(.*)', st)
                if match:
                    s_num = int(match.group(1))
                    s_desc = match.group(2).strip()
                else:
                    s_num = idx
                    s_desc = st.strip()
                action = "Navigate" if "navigate" in s_desc.lower() else ("Assert" if "assert" in s_desc.lower() or "verify" in s_desc.lower() else "Action")
                telemetry.log_step(
                    step_number=s_num,
                    action=action,
                    target=s_desc[:60],
                    outcome="Executed",
                    duration_ms=max(1, dur // max(len(step_lines), 1)),
                )
                test_cb("INFO", f"    [Step {s_num}] {action} -> {s_desc[:80]}")

            if not step_lines:
                telemetry.log_step(
                    step_number=1,
                    action="Pytest",
                    target=test_name,
                    outcome=f"Exit code: {proc.returncode}",
                    duration_ms=dur,
                )

            # Check if screenshot was captured by the spec's own screenshot code
            screenshot_path = None
            screenshot_match = re.search(r"\[FAILURE\] Diagnostic screenshot captured at\s+([^\s\n]+)", full_output)
            if screenshot_match:
                candidate = Path(screenshot_match.group(1).strip())
                if not candidate.is_absolute():
                    candidate = self.workspace_dir / candidate
                if candidate.exists():
                    screenshot_path = str(candidate)

            if not screenshot_path:
                for potential_dir in [self.screenshots_dir, self.workspace_dir / "test-results" / "screenshots"]:
                    if potential_dir.exists():
                        matching = list(potential_dir.glob(f"*{test_name}*.png")) or list(potential_dir.glob("*.png"))
                        if matching:
                            newest = max(matching, key=lambda p: p.stat().st_mtime)
                            if time.time() - newest.stat().st_mtime < 130:
                                screenshot_path = str(newest)
                                break

            if proc.returncode == 0:
                telemetry.mark_passed()
                test_cb("INFO", f"    [PASS] {test_name} passed ({dur}ms)")
            else:
                error_lines = [l[2:].strip() if l.startswith("E ") else l.strip() for l in stdout.splitlines() if l.startswith("E   ") or l.startswith("E ")]
                error_message = "\n".join(error_lines) if error_lines else ""
                if not error_message:
                    fail_lines = [l.strip() for l in stdout.splitlines() if "FAILED " in l or "AssertionError" in l or "Error:" in l]
                    error_message = "\n".join(fail_lines) if fail_lines else (stderr.strip() or stdout.strip()[-500:])

                classification = classify_failure(
                    error_message=error_message,
                    traceback_str=full_output,
                    page_url=self.target_url,
                )
                telemetry.mark_failed(
                    error_message=error_message,
                    traceback_str=full_output,
                    screenshot_path=screenshot_path,
                    page_url=self.target_url,
                    classification_data=classification,
                )
                test_cb("ERROR", f"    [FAIL] {test_name}: {error_message[:120]}")

        except subprocess.TimeoutExpired:
            dur = int((time.time() - t0) * 1000)
            err_msg = f"Test execution timed out after 120s: {test_name}"
            test_cb("ERROR", f"    [TIMEOUT] {err_msg}")
            classification = classify_failure(
                error_message=err_msg,
                traceback_str=err_msg,
                page_url=self.target_url,
            )
            telemetry.mark_failed(
                error_message=err_msg,
                traceback_str=err_msg,
                screenshot_path=None,
                page_url=self.target_url,
                classification_data=classification,
            )
        except Exception as exc:
            dur = int((time.time() - t0) * 1000)
            tb = traceback.format_exc()
            err_msg = str(exc)
            test_cb("ERROR", f"    [ERROR] Failed to execute {test_name}: {err_msg}")
            classification = classify_failure(
                error_message=err_msg,
                traceback_str=tb,
                page_url=self.target_url,
            )
            telemetry.mark_failed(
                error_message=err_msg,
                traceback_str=tb,
                screenshot_path=None,
                page_url=self.target_url,
                classification_data=classification,
            )


        out = telemetry.to_dict()
        out["file_name"] = file_path.name
        out["file_path"] = str(file_path)
        out["title"] = test_info.get("title") or test_name
        out["scenario_title"] = test_info.get("scenario_title")
        out["category"] = test_info.get("category", "functional")
        self._write_test_log_file(out)
        return out

    def _write_test_log_file(self, out: Dict[str, Any]):
        """Persists isolated, formatted per-testcase execution log to runs/<run_id>/test_logs/<test_name>.log"""
        test_name = out.get("test_name", "test")
        clean_name = "".join(c for c in test_name if c.isalnum() or c in ("-", "_")).strip() or "test"
        log_file = self.test_logs_dir / f"{clean_name}.log"

        lines = [
            "=" * 60,
            f"TESTCASE LOG: {test_name}",
            f"Title: {out.get('title', test_name)}",
            f"Scenario: {out.get('scenario_title', 'N/A')} (ID: {out.get('scenario_id', 'N/A')})",
            f"File: {out.get('file_name', 'N/A')} | Category: {out.get('category', 'functional')}",
            f"Status: {out.get('status', 'unknown').upper()} | Duration: {out.get('duration_ms', 0)}ms",
            f"Timestamp: {out.get('started_at', '')}",
            "=" * 60 + "\n",
        ]

        # Execution steps
        steps = out.get("steps") or []
        if steps:
            lines.append("--- STEP EXECUTION TRACE ---")
            for s in steps:
                st_num = s.get("step_number", 1)
                st_act = s.get("action", "")
                st_tgt = s.get("target", "")
                st_out = s.get("outcome", "")
                st_dur = s.get("duration_ms", 0)
                target_str = f" on '{st_tgt}'" if st_tgt else ""
                lines.append(f"[{s.get('status', 'PASSED').upper()}] Step {st_num}: {st_act}{target_str} -> {st_out} ({st_dur}ms)")
            lines.append("")

        # Network requests
        network_events = out.get("network_events") or []
        if network_events:
            lines.append("--- NETWORK REQUESTS ---")
            for n in network_events:
                lines.append(f"[{n.get('timestamp', '')}] {n.get('method', 'GET')} {n.get('url', '')} -> HTTP {n.get('status', 200)} ({n.get('duration_ms', 0)}ms)")
            lines.append("")

        # Console logs
        console_messages = out.get("console_messages") or []
        if console_messages:
            lines.append("--- BROWSER CONSOLE MESSAGES ---")
            for c in console_messages:
                lines.append(f"[{c.get('timestamp', '')}] [{str(c.get('type', 'info')).upper()}] {c.get('text', '')}")
            lines.append("")

        # Failure & Healer classification
        error_details = out.get("error_details")
        if error_details:
            lines.append("--- FAILURE DIAGNOSTICS & HEALER ATTRIBUTION ---")
            clf = error_details.get("classification") or {}
            lines.append(f"Classification: {clf.get('classification', 'UNKNOWN')} ({clf.get('subtype', 'N/A')})")
            lines.append(f"Summary: {clf.get('summary', '')}")
            if clf.get("root_cause_analysis"):
                lines.append(f"Root Cause: {clf.get('root_cause_analysis')}")
            if clf.get("suggested_fix"):
                lines.append(f"Suggested Fix: {clf.get('suggested_fix')}")
            if clf.get("alternative_selectors"):
                lines.append(f"Alternative Selectors: {', '.join(clf['alternative_selectors'])}")
            lines.append(f"Error Message: {error_details.get('error_message', '')}")
            if error_details.get("traceback"):
                lines.append(f"\nTraceback:\n{error_details['traceback']}")
            lines.append("")

        # Internal debug logs
        debug_logs = out.get("debug_logs") or []
        if debug_logs:
            lines.append("--- DETAILED DEBUG LOGS ---")
            for d in debug_logs:
                lines.append(f"[{d.get('timestamp', '')}] [{d.get('level', 'INFO')}] {d.get('message', '')}")
            lines.append("")

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            logger.warning(f"Could not write isolated test log file {log_file}: {e}")

    def _save_reports(self, full_results: Dict[str, Any], log_callback: Callable):
        """Saves results.json and report.html to runs/<run_id>/"""
        json_path = self.runs_dir / "results.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(full_results, f, indent=2, default=str)

        raw_logs = ""
        log_file = self.runs_dir / "execution.log"
        if log_file.exists():
            try:
                raw_logs = log_file.read_text(encoding="utf-8")
            except Exception:
                pass

        from app.core.report_generator import generate_html_report
        html_report = generate_html_report(
            results_data=full_results,
            project_name=f"Project {self.project_id[:8]}",
            target_url=self.target_url,
            run_id=self.run_id,
            raw_logs=raw_logs,
        )

        html_path = self.runs_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)

        log_callback("INFO", f"Generated Run Execution Report: runs/{self.run_id}/report.html")

import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

class FailureClassification:
    AUTOMATION_FAILURE = "AUTOMATION_FAILURE"
    APP_DEFECT = "APP_DEFECT"
    UNKNOWN = "UNKNOWN"

class FailureSubType:
    # Automation Failures
    LOCATOR_TIMEOUT = "LOCATOR_TIMEOUT"
    LOCATOR_NOT_FOUND = "LOCATOR_NOT_FOUND"
    ELEMENT_NOT_INTERACTABLE = "ELEMENT_NOT_INTERACTABLE"
    SCRIPT_SYNTAX_ERROR = "SCRIPT_SYNTAX_ERROR"
    NAVIGATION_TIMEOUT = "NAVIGATION_TIMEOUT"
    
    # Real Application Defects
    HTTP_SERVER_ERROR = "HTTP_SERVER_ERROR"          # 500, 502, 503, etc.
    SERVER_UNREACHABLE = "SERVER_UNREACHABLE"        # Connection refused, server offline
    UNCAUGHT_JS_EXCEPTION = "UNCAUGHT_JS_EXCEPTION"  # Window / React / Vue runtime error
    ASSERTION_FAILED = "ASSERTION_FAILED"            # Expected UI data/state mismatch
    APP_CRASH_BOUNDARY = "APP_CRASH_BOUNDARY"        # Error boundary rendered on page

def classify_failure(
    error_message: str,
    traceback_str: str = "",
    network_logs: Optional[List[Dict[str, Any]]] = None,
    console_logs: Optional[List[Dict[str, Any]]] = None,
    page_url: str = "",
    dom_snippet: str = "",
    element_candidates: Optional[List[Dict[str, Any]]] = None,
    debug_logs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Classifies a test failure into either:
    1. AUTOMATION_FAILURE: Broken test script, changed DOM selectors, timeout waiting for locator.
       Provides diagnostic context and alternative selector suggestions for the Healer Sub-Agent.
    2. APP_DEFECT: Genuine product bug (HTTP 500, server offline, unhandled frontend crash, assertion mismatch).
       Provides defect report context for engineering triage.
    """
    network_logs = network_logs or []
    console_logs = console_logs or []
    element_candidates = element_candidates or []
    debug_logs = debug_logs or []
    err_lower = (error_message or "").lower()
    tb_lower = (traceback_str or "").lower()

    # 0. Check for Server Offline / Connection Refused (Application Unreachable)
    if "connection refused" in err_lower or "err_connection_refused" in err_lower or "connectionerror" in tb_lower or "server is offline" in err_lower:
        return {
            "classification": FailureClassification.APP_DEFECT,
            "subtype": FailureSubType.SERVER_UNREACHABLE,
            "summary": f"Target application server is offline or unreachable: {page_url or 'Connection Refused'}",
            "confidence": 0.99,
            "root_cause_analysis": (
                f"The target application server at {page_url or 'target URL'} refused the connection. "
                "The server appears to be stopped, crashed, or not listening on the specified port. This is a critical application defect/outage."
            ),
            "healing_action": "ESCALATE_BUG",
            "healing_context": {
                "target_url": page_url,
                "error": error_message,
                "diagnosis": "Target application is offline / service unavailable.",
                "debug_trace": debug_logs[-5:] if debug_logs else [],
            },
        }

    # 1. Check for backend server error responses (HTTP 5xx)
    server_errors = [
        n for n in network_logs
        if isinstance(n, dict) and n.get("type") == "response" and int(n.get("status", 200)) >= 500
    ]
    if server_errors:
        latest = server_errors[-1]
        return {
            "classification": FailureClassification.APP_DEFECT,
            "subtype": FailureSubType.HTTP_SERVER_ERROR,
            "summary": f"Application backend returned HTTP {latest.get('status')} at {latest.get('url')}",
            "confidence": 0.95,
            "root_cause_analysis": (
                f"The test interacted with the application, but the server failed with HTTP {latest.get('status')}. "
                f"Response preview: {latest.get('body_preview', 'N/A')}. This represents a genuine application backend failure."
            ),
            "healing_action": "ESCALATE_BUG",
            "healing_context": {
                "server_error_url": latest.get("url"),
                "status_code": latest.get("status"),
                "response_preview": latest.get("body_preview"),
                "console_errors": [c for c in console_logs if str(c.get("type", "")).lower() in ["error", "warning"]],
            },
        }

    # 2. Check for uncaught client-side JS crash / pageerror
    fatal_console = [
        c for c in console_logs
        if isinstance(c, dict) and (
            "uncaught" in str(c.get("text", "")).lower()
            or "typeerror" in str(c.get("text", "")).lower()
            or "referenceerror" in str(c.get("text", "")).lower()
            or "unhandled" in str(c.get("text", "")).lower()
        )
    ]
    if fatal_console and ("crash" in err_lower or "evaluat" in tb_lower or "500" in tb_lower):
        return {
            "classification": FailureClassification.APP_DEFECT,
            "subtype": FailureSubType.UNCAUGHT_JS_EXCEPTION,
            "summary": f"Uncaught frontend script exception: {fatal_console[-1].get('text', '')[:120]}",
            "confidence": 0.88,
            "root_cause_analysis": (
                "The browser page threw an uncaught JavaScript runtime exception that disrupted application execution."
            ),
            "healing_action": "ESCALATE_BUG",
            "healing_context": {"fatal_console_messages": fatal_console},
        }

    # 3. Check for Assertion Failure (App defect or semantic regression)
    if "assertionerror" in tb_lower or "assert" in err_lower:
        expected_match = re.search(r"expected:?\s*(.*?)(?:to|but|\n|$)", error_message, re.IGNORECASE)
        actual_match = re.search(r"actual|received:?\s*(.*?)(?:\n|$)", error_message, re.IGNORECASE)
        expected_val = expected_match.group(1).strip() if expected_match else None
        actual_val = actual_match.group(1).strip() if actual_match else None

        return {
            "classification": FailureClassification.APP_DEFECT,
            "subtype": FailureSubType.ASSERTION_FAILED,
            "summary": f"Assertion check failed: {error_message.strip()[:140]}",
            "confidence": 0.85,
            "root_cause_analysis": (
                "The application flow completed the interaction, but the resulting page state or data "
                "did not match the specified expected outcome."
            ),
            "healing_action": "VERIFY_OR_HEAL_SPEC",
            "healing_context": {
                "expected": expected_val,
                "actual": actual_val,
                "assertion_statement": error_message.strip(),
                "suggested_fix": (
                    f"If the application behavior changed intentionally, update assertion expected value from '{expected_val}' to '{actual_val}'."
                    if expected_val and actual_val else "Inspect actual vs expected page state and verify if UI layout or copy updated."
                ),
            },
        }

    # 4. Check for Locator / Selector Timeouts (Automation Failure with Healer Matching)
    target_selector = None
    sel_extract = re.search(r"(?:locator|selector|waiting for)\s*\(?['\"]([#.a-zA-Z0-9_\-\[\]=: ]+)['\"]", error_message, re.IGNORECASE) or \
                  re.search(r"(?:locator|selector|waiting for)\s*\(?['\"]([#.a-zA-Z0-9_\-\[\]=: ]+)['\"]", traceback_str, re.IGNORECASE)
    if sel_extract:
        target_selector = sel_extract.group(1)
    else:
        quoted = re.search(r"['\"]([#.a-zA-Z0-9_\-\[\]=: ]{2,50})['\"]", error_message)
        if quoted:
            target_selector = quoted.group(1)

    if "timeout" in err_lower and ("locator" in err_lower or "selector" in err_lower or "waiting for" in err_lower or "click" in tb_lower or "fill" in tb_lower):
        # Match target_selector against available element candidates in DOM
        alternative_selectors = []
        matching_candidates = []
        if target_selector and element_candidates:
            clean_term = re.sub(r"[#._\-\[\]=:]", " ", target_selector).lower()
            tokens = [w for w in clean_term.split() if len(w) > 2]
            for cand in element_candidates:
                cand_text = str(cand.get("text", "")).lower()
                cand_id = str(cand.get("id", "")).lower()
                cand_name = str(cand.get("name", "")).lower()
                cand_tag = str(cand.get("tag", "")).lower()
                cand_role = str(cand.get("role", "")).lower()
                cand_type = str(cand.get("type", "")).lower()
                cand_testid = str(cand.get("testid", "")).lower()

                score = 0
                for tok in tokens:
                    if tok in cand_text or tok in cand_id or tok in cand_name or tok in cand_role or tok in cand_type or tok in cand_testid:
                        score += 1

                if score > 0 or (cand_tag in ["button", "input", "a"] and len(matching_candidates) < 4):
                    matching_candidates.append(cand)
                    if cand.get("testid"):
                        alternative_selectors.append(f"[data-testid='{cand['testid']}']")
                    if cand.get("id"):
                        alternative_selectors.append(f"#{cand['id']}")
                    elif cand.get("text") and len(cand["text"].strip()) < 30:
                        alternative_selectors.append(f"{cand_tag}:has-text(\"{cand['text'].strip()}\")")
                    elif cand.get("name"):
                        alternative_selectors.append(f"{cand_tag}[name=\"{cand['name']}\"]")
                    elif cand.get("role"):
                        alternative_selectors.append(f"role={cand['role']}")

        suggested_fix = None
        if alternative_selectors:
            suggested_fix = f"Replace broken selector '{target_selector}' with resilient alternative: '{alternative_selectors[0]}'"
        elif target_selector:
            suggested_fix = f"Element '{target_selector}' was not found. Inspect live DOM candidates to re-anchor locator."

        matched_el = matching_candidates[0] if matching_candidates else (element_candidates[0] if element_candidates else None)
        return {
            "classification": FailureClassification.AUTOMATION_FAILURE,
            "subtype": FailureSubType.LOCATOR_TIMEOUT,
            "summary": f"Locator timeout: Unable to resolve element `{target_selector or 'target'}` within timeout",
            "confidence": 0.92,
            "alternative_selectors": alternative_selectors[:5],
            "suggested_fix": suggested_fix,
            "root_cause_analysis": (
                f"The test script attempted to interact with element `{target_selector}`, but the element was not found in the DOM "
                "or was not interactable. This is typically caused by UI changes, dynamic ID changes, or DOM restructuring."
            ),
            "healing_action": "HEAL_LOCATOR",
            "healing_context": {
                "broken_selector": target_selector,
                "suggested_fix": suggested_fix,
                "alternative_selectors": alternative_selectors[:5],
                "candidate_elements": matching_candidates[:6] if matching_candidates else element_candidates[:6],
                "matched_element": matched_el,
                "page_url": page_url,
                "dom_snippet": dom_snippet[:800] if dom_snippet else None,
                "suggested_actions": [
                    f"Use resilient alternative selector: {alternative_selectors[0]}" if alternative_selectors else "Use get_by_role or text-based locator",
                    "Verify if element is dynamically loaded or inside a modal/iframe",
                    "Check if preceding navigation step completed fully",
                ],
            },
        }

    if "navigation" in err_lower and "timeout" in err_lower:
        return {
            "classification": FailureClassification.AUTOMATION_FAILURE,
            "subtype": FailureSubType.NAVIGATION_TIMEOUT,
            "summary": f"Page navigation timed out loading `{page_url or 'target URL'}`",
            "confidence": 0.80,
            "root_cause_analysis": "The target page took longer than the configured timeout to complete domcontentloaded.",
            "healing_action": "HEAL_TIMEOUT_OR_WAIT",
            "healing_context": {"page_url": page_url, "suggested_fix": "Increase page navigation timeout or use wait_until='load'"},
        }

    if "syntaxerror" in tb_lower or "attributeerror" in tb_lower or "nameerror" in tb_lower:
        return {
            "classification": FailureClassification.AUTOMATION_FAILURE,
            "subtype": FailureSubType.SCRIPT_SYNTAX_ERROR,
            "summary": f"Script syntax or runtime error in test file: {error_message[:120]}",
            "confidence": 0.95,
            "root_cause_analysis": "The generated test file contains invalid Python code, undefined variables, or invalid Playwright method calls.",
            "healing_action": "HEAL_SCRIPT_SYNTAX",
            "healing_context": {"error": error_message, "suggested_fix": "Regenerate or correct test function syntax and Playwright imports."},
        }

    # Default fallback classification
    return {
        "classification": FailureClassification.UNKNOWN,
        "subtype": "GENERIC_ERROR",
        "summary": error_message[:140] if error_message else "Unspecified test failure",
        "confidence": 0.50,
        "root_cause_analysis": "Could not conclusively distinguish between automation failure and application defect.",
        "healing_action": "MANUAL_REVIEW",
        "healing_context": {
            "error_message": error_message,
            "traceback": traceback_str[:600],
            "debug_trace": debug_logs[-5:] if debug_logs else [],
        },
    }


class TestTelemetryLogger:
    """
    In-memory and file-based structured step logger designed to be called
    during Playwright test execution. Records detailed step execution breadcrumbs,
    microsecond timings, DOM candidates, network status, and failure artifacts.
    """
    __test__ = False

    def __init__(self, test_name: str, scenario_id: Optional[str] = None):
        self.test_name = test_name
        self.scenario_id = scenario_id
        self.started_at = datetime.utcnow()
        self.steps: List[Dict[str, Any]] = []
        self.debug_logs: List[Dict[str, Any]] = []
        self.network_events: List[Dict[str, Any]] = []
        self.console_messages: List[Dict[str, Any]] = []
        self.element_candidates: List[Dict[str, Any]] = []
        self.dom_snapshot: Optional[str] = None
        self.status = "running"
        self.duration_ms = 0
        self.error_details: Optional[Dict[str, Any]] = None
        self.screenshot_path: Optional[str] = None

    def log_step(self, step_number: int, action: str, target: str = "", outcome: str = "", duration_ms: int = 0):
        self.steps.append({
            "step_number": step_number,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "target": target,
            "outcome": outcome,
            "duration_ms": duration_ms,
            "status": "passed",
        })
        self.log_debug("INFO", f"Step {step_number} [{action}] on '{target}' -> {outcome} ({duration_ms}ms)")

    def log_debug(self, level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        self.debug_logs.append({
            "timestamp": datetime.utcnow().strftime("%H:%M:%S.%f")[:-3],
            "level": level.upper(),
            "message": message,
            "metadata": metadata or {},
        })

    def log_network(self, method: str, url: str, status: int, duration_ms: int = 0, preview: str = ""):
        self.network_events.append({
            "timestamp": datetime.utcnow().strftime("%H:%M:%S.%f")[:-3],
            "type": "response",
            "method": method,
            "url": url,
            "status": status,
            "duration_ms": duration_ms,
            "body_preview": preview[:300] if preview else "",
        })

    def log_console(self, msg_type: str, text: str, location: str = ""):
        self.console_messages.append({
            "timestamp": datetime.utcnow().strftime("%H:%M:%S.%f")[:-3],
            "type": msg_type,
            "text": text,
            "location": location,
        })

    def set_dom_context(self, dom_snippet: str, element_candidates: Optional[List[Dict[str, Any]]] = None):
        self.dom_snapshot = dom_snippet
        if element_candidates:
            self.element_candidates = element_candidates

    def mark_passed(self):
        self.status = "passed"
        self.duration_ms = int((datetime.utcnow() - self.started_at).total_seconds() * 1000)
        self.log_debug("INFO", f"Test {self.test_name} completed successfully in {self.duration_ms}ms")

    def mark_failed(
        self,
        error_message: str,
        traceback_str: str = "",
        screenshot_path: Optional[str] = None,
        classification_data: Optional[Dict[str, Any]] = None,
        page_url: str = "",
    ):
        self.status = "failed"
        self.duration_ms = int((datetime.utcnow() - self.started_at).total_seconds() * 1000)
        self.screenshot_path = screenshot_path

        classification = classification_data or classify_failure(
            error_message=error_message,
            traceback_str=traceback_str,
            network_logs=self.network_events,
            console_logs=self.console_messages,
            page_url=page_url,
            dom_snippet=self.dom_snapshot or "",
            element_candidates=self.element_candidates,
            debug_logs=self.debug_logs,
        )

        self.error_details = {
            "error_message": error_message,
            "traceback": traceback_str,
            "classification": classification,
            "alternative_selectors": classification.get("alternative_selectors", []),
            "suggested_fix": classification.get("suggested_fix"),
            "healing_context": classification.get("healing_context"),
        }
        self.log_debug("ERROR", f"Test {self.test_name} failed: {error_message}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat(),
            "steps": self.steps,
            "debug_logs": self.debug_logs,
            "network_events": self.network_events,
            "console_messages": self.console_messages,
            "element_candidates": self.element_candidates,
            "dom_snapshot": self.dom_snapshot,
            "error_details": self.error_details,
            "screenshot_path": self.screenshot_path,
        }

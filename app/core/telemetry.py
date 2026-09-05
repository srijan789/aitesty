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
) -> Dict[str, Any]:
    """
    Classifies a test failure into either:
    1. AUTOMATION_FAILURE: Broken test script, changed DOM selectors, timeout waiting for locator.
       Provides diagnostic context for the Healer Sub-Agent to repair the testcase.
    2. APP_DEFECT: Genuine product bug (HTTP 500, server offline, unhandled frontend crash, assertion mismatch).
       Provides defect report context for engineering triage.
    """
    network_logs = network_logs or []
    console_logs = console_logs or []
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
        # Extract expected vs actual if possible
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
            },
        }

    # 4. Check for Locator / Selector Timeouts (Automation Failure)
    locator_pattern = re.compile(r"(?:waiting for (?:locator|selector)|locator\((['\"].*?['\"])\)|Page\.click: Timeout|Page\.fill: Timeout)", re.IGNORECASE)
    loc_match = locator_pattern.search(error_message) or locator_pattern.search(traceback_str)

    target_selector = None
    if loc_match:
        # Try to extract the selector string
        sel_extract = re.search(r"['\"]([#.a-zA-Z0-9_\-\[\]=: ]+)['\"]", loc_match.group(0))
        if sel_extract:
            target_selector = sel_extract.group(1)

    if "timeout" in err_lower and ("locator" in err_lower or "selector" in err_lower or "waiting for" in err_lower or "click" in tb_lower or "fill" in tb_lower):
        return {
            "classification": FailureClassification.AUTOMATION_FAILURE,
            "subtype": FailureSubType.LOCATOR_TIMEOUT,
            "summary": f"Locator timeout: Unable to resolve element `{target_selector or 'target'}` within timeout",
            "confidence": 0.92,
            "root_cause_analysis": (
                f"The test script attempted to interact with element `{target_selector}`, but the element was not found in the DOM "
                "or was not interactable. This is typically caused by UI changes, dynamic ID changes, or DOM restructuring."
            ),
            "healing_action": "HEAL_LOCATOR",
            "healing_context": {
                "broken_selector": target_selector,
                "page_url": page_url,
                "dom_snippet": dom_snippet[:500] if dom_snippet else None,
                "suggested_actions": [
                    "Inspect current live DOM for alternative resilient attributes (e.g. data-testid, aria-label, role, visible text)",
                    "Verify if element is inside an iframe or shadow DOM",
                    "Check if navigation occurred before element appeared",
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
            "healing_context": {"page_url": page_url},
        }

    if "syntaxerror" in tb_lower or "attributeerror" in tb_lower or "nameerror" in tb_lower:
        return {
            "classification": FailureClassification.AUTOMATION_FAILURE,
            "subtype": FailureSubType.SCRIPT_SYNTAX_ERROR,
            "summary": f"Script syntax or runtime error in test file: {error_message[:120]}",
            "confidence": 0.95,
            "root_cause_analysis": "The generated test file contains invalid Python code, undefined variables, or invalid Playwright method calls.",
            "healing_action": "HEAL_SCRIPT_SYNTAX",
            "healing_context": {"error": error_message},
        }

    # Default fallback classification
    return {
        "classification": FailureClassification.UNKNOWN,
        "subtype": "GENERIC_ERROR",
        "summary": error_message[:140] if error_message else "Unspecified test failure",
        "confidence": 0.50,
        "root_cause_analysis": "Could not conclusively distinguish between automation failure and application defect.",
        "healing_action": "MANUAL_REVIEW",
        "healing_context": {"error_message": error_message, "traceback": traceback_str[:600]},
    }


class TestTelemetryLogger:
    """
    In-memory and file-based structured step logger designed to be called
    during Playwright test execution. Records detailed step execution breadcrumbs,
    timings, network status, and failure artifacts.
    """
    __test__ = False


    def __init__(self, test_name: str, scenario_id: Optional[str] = None):
        self.test_name = test_name
        self.scenario_id = scenario_id
        self.started_at = datetime.utcnow()
        self.steps: List[Dict[str, Any]] = []
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

    def mark_passed(self):
        self.status = "passed"
        self.duration_ms = int((datetime.utcnow() - self.started_at).total_seconds() * 1000)

    def mark_failed(
        self,
        error_message: str,
        traceback_str: str = "",
        screenshot_path: Optional[str] = None,
        classification_data: Optional[Dict[str, Any]] = None,
    ):
        self.status = "failed"
        self.duration_ms = int((datetime.utcnow() - self.started_at).total_seconds() * 1000)
        self.screenshot_path = screenshot_path
        self.error_details = {
            "error_message": error_message,
            "traceback": traceback_str,
            "classification": classification_data or classify_failure(error_message, traceback_str),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat(),
            "steps": self.steps,
            "error_details": self.error_details,
            "screenshot_path": self.screenshot_path,
        }

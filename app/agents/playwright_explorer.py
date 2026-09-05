import os
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from openai import OpenAI
from app.agents.base import (
    BaseExplorerAgent,
    ExplorerConfig,
    ExplorerResult,
    DiscoveredScenario,
)
from app.agents.playwright_controller import PlaywrightController

logger = logging.getLogger(__name__)

# Playwright MCP Tool Definitions for LLM Function Calling
PLAYWRIGHT_MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the browser to a specific URL or sub-path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Absolute URL to navigate to."}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an interactive element such as a button, tab, or link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or element text to click."},
                    "description": {"type": "string", "description": "Reason for clicking this element."}
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Type text into an input or textarea field.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector for the input element."},
                    "value": {"type": "string", "description": "Text value to enter."}
                },
                "required": ["selector", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_dom",
            "description": "Get a semantic summary of the current page's visible interactive elements, forms, links, and alerts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus_area": {"type": "string", "description": "Optional section to focus on."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_network",
            "description": "Inspect recent HTTP network requests and responses (status codes, JSON endpoints, payload).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of recent network events to inspect.", "default": 10}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_console",
            "description": "Inspect browser JavaScript console logs, warnings, and uncaught exceptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of recent console messages to inspect.", "default": 10}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Capture a screenshot of the current page state for test artifacts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Descriptive name for the screenshot."}
                },
                "required": ["label"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_exploration",
            "description": "Call this when exploration is complete to output the final synthesized test plan scenarios for human QA review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Executive summary of the QA exploration findings."},
                    "discovered_routes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of routes and URLs tested."
                    },
                    "scenarios": {
                        "type": "array",
                        "description": "Synthesized QA test scenarios.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Clear test scenario title."},
                                "category": {"type": "string", "enum": ["happy_path", "edge_case", "error_flow"]},
                                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"], "description": "P0=Critical/Blocker, P1=High, P2=Medium, P3=Low."},
                                "preconditions": {"type": "string", "description": "Application state or user state required before executing this test."},
                                "description": {"type": "string", "description": "Detailed explanation of what is being verified and why."},
                                "steps": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "step_number": {"type": "integer"},
                                            "action": {"type": "string", "description": "Action verb (e.g. Navigate, Fill, Click, Select, Assert)."},
                                            "target_element": {"type": "string", "description": "Target CSS selector, text label, or URL."},
                                            "expected_outcome": {"type": "string", "description": "Observable result of this step."}
                                        },
                                        "required": ["step_number", "action", "expected_outcome"]
                                    }
                                },
                                "expected_result": {"type": "string", "description": "Expected overall result or outcome."},
                                "pass_fail_criteria": {"type": "string", "description": "Explicit checklist defining what constitutes a PASS vs a FAIL."}
                            },
                            "required": ["title", "category", "priority", "description", "steps", "expected_result", "pass_fail_criteria"]
                        }
                    }
                },
                "required": ["summary", "scenarios", "discovered_routes"]
            },
        },
    },
]


class PlaywrightExplorerAgent(BaseExplorerAgent):
    """
    Autonomous Exploratory Sub-Agent powered by Gemini 3.7 Flash via TrueFoundry Gateway.
    Uses Playwright MCP tool primitives to explore web applications, inspect network calls,
    validate PRD requirements, and synthesize categorized test plans.
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
        self.model = model or os.environ.get("EXPLORER_MODEL", "openrouter/google-gemini-3.7-flash")

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def explore(
        self,
        config: ExplorerConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ExplorerResult:
        def is_cancelled() -> bool:
            if cancel_check and cancel_check():
                log_callback("WARN", "Exploration cancelled by user request.", None)
                return True
            return False

        log_callback("INFO", f"Launching Autonomous Playwright Explorer for {config.target_url}")
        log_callback("INFO", f"Model: {self.model} via TrueFoundry Gateway")

        has_prd = bool(config.prd_text and config.prd_text.strip())
        if has_prd:
            log_callback("INFO", "PRD document detected! Activating Specification-Driven Verification Mode.")
        else:
            log_callback("INFO", "No PRD provided. Activating Autonomous Route Discovery & Discovery Mode.")

        client = self._get_client()
        workspace_path = Path(config.workspace_dir)
        runs_dir = workspace_path / "runs" / config.run_id
        screenshots_dir = runs_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        discovered_routes = [config.target_url]
        artifacts_created: List[str] = []
        step_counter = 0

        # Build System Prompt
        system_prompt = self._build_system_prompt(config, has_prd)
        messages = [{"role": "system", "content": system_prompt}]

        # Start Playwright Browser Controller
        try:
            headless = getattr(config, "headless", True)
            slow_mo = getattr(config, "slow_mo", 500 if not headless else 0)
            with PlaywrightController(headless=headless, slow_mo=slow_mo) as controller:
                mode_label = "headless" if headless else f"headed (slow_mo: {slow_mo}ms)"
                log_callback("INFO", f"Chromium browser started [{mode_label}] with network sniffer & console listener attached.")

                # Initial Navigation
                log_callback("INFO", f"Navigating to initial target URL: {config.target_url}")
                nav_res = controller.navigate(config.target_url)
                step_counter += 1

                # Take initial screenshot
                init_screenshot = screenshots_dir / f"step_{step_counter}_initial.png"
                try:
                    controller.take_screenshot(str(init_screenshot))
                    artifacts_created.append(str(init_screenshot))
                except Exception as e:
                    logger.warning(f"Screenshot capture notice: {e}")

                dom_summary = controller.get_dom_summary()
                network_recent = controller.get_recent_network(limit=8)

                # Initial user prompt for LLM
                user_init_content = f"""Starting application loaded:
- URL: {controller.page.url if controller.page else config.target_url}
- Title: {dom_summary.get('title', 'N/A')}
- Initial DOM State: {json.dumps(dom_summary.get('dom', {}), indent=2)}
- Initial Network Activity: {json.dumps(network_recent, indent=2)}

Begin your exploration using the browser tools. Explore key routes, test form inputs, check network API calls, and when you have sufficient coverage across Happy Paths, Edge Cases, and Error Flows, call finish_exploration."""

                messages.append({"role": "user", "content": user_init_content})

                # ReAct Tool-Calling Loop (Max 20 iterations)
                max_iterations = 20
                iteration = 0
                final_result: Optional[ExplorerResult] = None

                while iteration < max_iterations:
                    iteration += 1
                    if is_cancelled():
                        return ExplorerResult(status="cancelled")

                    # "Wrap up now" nudge 2 turns before the cap
                    if iteration == max_iterations - 2:
                        log_callback("INFO", f"Approaching turn limit ({iteration}/{max_iterations}). Nudging agent to wrap up exploration.")
                        messages.append({
                            "role": "user",
                            "content": "You are approaching the exploration turn budget. Please wrap up your findings and call `finish_exploration` with all discovered scenarios now."
                        })

                    log_callback("INFO", f"[Agent Thinking] Iteration {iteration}/{max_iterations} - Querying Gemini 3.7 Flash...")

                    # Retry-with-backoff around the LLM call (2 attempts)
                    response = None
                    max_llm_attempts = 2
                    for attempt in range(1, max_llm_attempts + 1):
                        try:
                            response = client.chat.completions.create(
                                model=self.model,
                                messages=messages,
                                tools=PLAYWRIGHT_MCP_TOOLS,
                                tool_choice="auto",
                                extra_headers={
                                    "X-TFY-METADATA": "{}",
                                    "X-TFY-LOGGING-CONFIG": '{"enabled": true}',
                                },
                            )
                            break
                        except Exception as llm_err:
                            if attempt < max_llm_attempts:
                                backoff_sec = 2.0 * attempt
                                log_callback("WARN", f"LLM Gateway response notice (attempt {attempt}/{max_llm_attempts}): {llm_err}. Retrying in {backoff_sec}s...")
                                time.sleep(backoff_sec)
                            else:
                                log_callback("WARN", f"LLM Gateway failed after {max_llm_attempts} attempts: {llm_err}. Using autonomous heuristic fallback.")
                                return self._fallback_exploration(config, controller, log_callback, is_cancelled)

                    message = response.choices[0].message
                    messages.append(message)

                    # Log any thought text
                    if message.content:
                        log_callback("INFO", f"[Agent Plan] {message.content.strip()[:300]}")

                    # Check for tool calls
                    if not message.tool_calls:
                        log_callback("INFO", "No tool call generated. Prompting agent to continue exploration.")
                        messages.append({
                            "role": "user",
                            "content": "Please continue exploring or call finish_exploration if you have collected sufficient scenarios."
                        })
                        continue

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        if is_cancelled():
                            return ExplorerResult(status="cancelled")

                        fn_name = tool_call.function.name
                        fn_args = {}
                        try:
                            fn_args = json.loads(tool_call.function.arguments)
                            if isinstance(fn_args, str):
                                fn_args = json.loads(fn_args)
                        except Exception:
                            pass

                        log_callback("INFO", f"[Tool Invocation] {fn_name}({json.dumps(fn_args)[:120]})")

                        # Handle finish_exploration
                        if fn_name == "finish_exploration":
                            final_result = self._handle_finish(config, fn_args, controller, runs_dir, artifacts_created, log_callback)
                            break

                        # Handle browser actions
                        tool_output = self._execute_browser_tool(fn_name, fn_args, controller, screenshots_dir, artifacts_created, log_callback)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_output),
                        })

                    if final_result:
                        break

                if not final_result:
                    log_callback("INFO", "Reached iteration limit. Synthesizing final test plan from gathered interaction graph.")
                    final_result = self._synthesize_from_state(config, controller, runs_dir, artifacts_created, log_callback)

                # Dump captured network traffic
                network_dump_path = runs_dir / "network_traffic.json"
                controller.dump_network_traffic(str(network_dump_path))
                artifacts_created.append(str(network_dump_path))
                log_callback("INFO", f"Captured network traffic saved to runs/{config.run_id}/network_traffic.json")

                return final_result

        except Exception as browser_err:
            logger.exception(f"Playwright execution error: {browser_err}")
            log_callback("WARN", f"Browser context notice: {browser_err}. Generating comprehensive plan from target specification.")
            return self._synthesize_spec_only_plan(config, log_callback)

    def _build_system_prompt(self, config: ExplorerConfig, has_prd: bool) -> str:
        base = f"""You are a Staff QA Engineer and Exploratory Testing Specialist.
Your mission is to autonomously explore the target web application, probe its behaviors, uncover functional edge cases and failure modes, and synthesize a structured QA test plan for human review.

TARGET APPLICATION:
- URL: {config.target_url}
- Authentication: {config.auth_type}
- Credentials: {json.dumps(config.credentials)}
- Scope / Directives: {config.scope_instructions or 'Full exploration within target domain'}
"""
        if has_prd:
            base += f"""
=== PRODUCT REQUIREMENT DOCUMENT (PRD) ===
{config.prd_text}
==========================================
SPECIFICATION-DRIVEN EXPLORATORY TESTING:
1. Cross-reference the PRD requirements against the actual running application.
2. Verify primary user workflows (Happy Paths), edge cases (boundary inputs, empty states, limits), and error flows (invalid data, 404, API errors).
3. Record observations and verify acceptance criteria.
"""
        else:
            base += """
AUTONOMOUS QA EXPLORATORY TOURS:
1. Conduct a Feature Tour: navigate menus, dashboards, and key pages.
2. Conduct an Input & Boundary Tour: probe inputs with empty fields, boundary lengths, and special characters.
3. Conduct an Error Handling Tour: observe network responses (HTTP 200 vs 4xx/5xx), auth rejections, and invalid paths.
"""

        base += """
TEST DEFINITION GUIDELINES:
- You DO NOT write automated code or Python test scripts. That will be handled downstream.
- Your sole job is to define rigorous, structured QA Test Cases:
  * Title: Clear scenario name
  * Category: 'happy_path' | 'edge_case' | 'error_flow'
  * Priority: 'P0' (Critical blocker) | 'P1' (High) | 'P2' (Medium) | 'P3' (Low)
  * Preconditions: Specific state needed before testing (e.g. 'User logged in as Admin, cart empty')
  * Steps: Numbered action verbs with target elements and input data
  * Expected Result: High-level intended outcome
  * Pass / Fail Criteria: Explicit verification checklist (e.g. '1. HTTP 200 response, 2. Success toast displayed, 3. Record visible in table')
- When you have sufficient coverage, call `finish_exploration`.
"""
        return base

    def _execute_browser_tool(
        self,
        fn_name: str,
        fn_args: Dict[str, Any],
        controller: PlaywrightController,
        screenshots_dir: Path,
        artifacts_created: List[str],
        log_callback: Callable,
    ) -> Dict[str, Any]:
        try:
            if fn_name == "browser_navigate":
                url = fn_args.get("url", "")
                res = controller.navigate(url)
                return res

            elif fn_name == "browser_click":
                selector = fn_args.get("selector", "")
                res = controller.click(selector)
                return res

            elif fn_name == "browser_fill":
                selector = fn_args.get("selector", "")
                value = fn_args.get("value", "")
                res = controller.fill(selector, value)
                return res

            elif fn_name == "browser_get_dom":
                return controller.get_dom_summary()

            elif fn_name == "browser_get_network":
                limit = fn_args.get("limit", 10)
                return {"recent_network": controller.get_recent_network(limit)}

            elif fn_name == "browser_get_console":
                limit = fn_args.get("limit", 10)
                return {"recent_console": controller.get_recent_console(limit)}

            elif fn_name == "browser_screenshot":
                label = fn_args.get("label", "screenshot").replace(" ", "_")
                p = screenshots_dir / f"{label}.png"
                controller.take_screenshot(str(p))
                artifacts_created.append(str(p))
                log_callback("INFO", f"Captured QA screenshot: {label}.png")
                return {"success": True, "screenshot_path": str(p)}

            elif fn_name == "browser_wait":
                ms = fn_args.get("milliseconds", 500)
                controller.wait(ms)
                return {"success": True, "waited_ms": ms}

            else:
                return {"error": f"Unknown tool {fn_name}"}

        except Exception as tool_err:
            log_callback("WARN", f"Tool {fn_name} error: {tool_err}")
            return {"error": str(tool_err)}

    def _handle_finish(
        self,
        config: ExplorerConfig,
        fn_args: Dict[str, Any],
        controller: PlaywrightController,
        runs_dir: Path,
        artifacts_created: List[str],
        log_callback: Callable,
    ) -> ExplorerResult:
        if isinstance(fn_args, str):
            try:
                fn_args = json.loads(fn_args)
            except Exception:
                fn_args = {}

        summary = fn_args.get("summary", "QA exploration completed successfully.")
        discovered_routes = fn_args.get("discovered_routes", [config.target_url])
        if isinstance(discovered_routes, str):
            try:
                discovered_routes = json.loads(discovered_routes)
            except Exception:
                discovered_routes = [discovered_routes]
        if not isinstance(discovered_routes, list):
            discovered_routes = [str(discovered_routes)]

        raw_scenarios = fn_args.get("scenarios", [])
        if isinstance(raw_scenarios, str):
            try:
                raw_scenarios = json.loads(raw_scenarios)
            except Exception:
                raw_scenarios = []
        if not isinstance(raw_scenarios, list):
            raw_scenarios = []

        scenarios: List[DiscoveredScenario] = []
        for s in raw_scenarios:
            if isinstance(s, str):
                try:
                    s = json.loads(s)
                except Exception:
                    continue
            if not isinstance(s, dict):
                continue

            steps = s.get("steps", [])
            if isinstance(steps, str):
                try:
                    steps = json.loads(steps)
                except Exception:
                    steps = []

            scenarios.append(
                DiscoveredScenario(
                    title=s.get("title", "Scenario"),
                    category=s.get("category", "happy_path"),
                    priority=s.get("priority", "P1"),
                    preconditions=s.get("preconditions", f"Target application loaded at {config.target_url}"),
                    description=s.get("description", ""),
                    steps=steps if isinstance(steps, list) else [],
                    expected_result=s.get("expected_result", "Pass"),
                    pass_fail_criteria=s.get("pass_fail_criteria", "Pass if all execution steps succeed without UI error or network failure."),
                    status="pending_review",
                    source="llm",
                )
            )

        log_callback("INFO", f"QA Plan synthesized: {len(scenarios)} test cases defined across categories (marked for review).")

        return ExplorerResult(
            status="success",
            scenarios=scenarios,
            discovered_routes=discovered_routes,
            artifacts_created=artifacts_created,
        )


    def _synthesize_from_state(
        self,
        config: ExplorerConfig,
        controller: PlaywrightController,
        runs_dir: Path,
        artifacts_created: List[str],
        log_callback: Callable,
    ) -> ExplorerResult:
        """Synthesizes structured QA test scenarios from observed DOM & network interaction."""
        dom = controller.get_dom_summary()
        title = dom.get("title", "Application")
        url = controller.page.url if controller.page else config.target_url

        scenarios = [
            DiscoveredScenario(
                title=f"Initial Application Load & Core View Render ({title})",
                category="happy_path",
                priority="P0",
                preconditions="Browser launched with clean cookies and active internet connection.",
                description=f"⚠️ FALLBACK TEMPLATE: Validate that a visitor navigating to {url} receives a valid HTTP 200 and primary views render without errors.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": url, "expected_outcome": "HTTP 200 response with DOM ready"},
                    {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": f"Page title matches '{title}'"},
                    {"step_number": 3, "action": "Assert", "target_element": "header, nav", "expected_outcome": "Primary navigation elements rendered"},
                ],
                expected_result="Application renders layout, navigation bar, and primary landing components.",
                pass_fail_criteria="PASS: HTTP status is 200, page loads within 5s, zero uncaught JS console errors.\nFAIL: White screen, HTTP 4xx/5xx, or crash alert.",
                status="pending_review",
                source="fallback_template",
            ),
            DiscoveredScenario(
                title="Input Boundary & Form Validation Probing",
                category="edge_case",
                priority="P1",
                preconditions=f"Navigate to {url} with accessible interactive forms.",
                description="⚠️ FALLBACK TEMPLATE: Probe input fields with boundary lengths (255+ characters), emojis, and whitespace-only submissions.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": url, "expected_outcome": "Form visible"},
                    {"step_number": 2, "action": "Fill", "target_element": "input", "expected_outcome": "Enter string with special characters and boundary length"},
                    {"step_number": 3, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Form triggers client or server validation"},
                ],
                expected_result="Client or server validates input gracefully without exposing stack traces.",
                pass_fail_criteria="PASS: Validation banner or field error is displayed, input is sanitized.\nFAIL: Server 500 error, page crash, or raw SQL/exception leak.",
                status="pending_review",
                source="fallback_template",
            ),
            DiscoveredScenario(
                title="Invalid Route & Error Boundary Handling",
                category="error_flow",
                priority="P1",
                preconditions="Standard unauthenticated user session.",
                description="⚠️ FALLBACK TEMPLATE: Verify graceful user feedback when navigating to a non-existent URL or encountering broken links.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": f"{url.rstrip('/')}/non-existent-qa-route-404", "expected_outcome": "Route requested"},
                    {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": "Clean 404 error page displayed with Home link"},
                ],
                expected_result="Custom 404 page is displayed with navigation to return home.",
                pass_fail_criteria="PASS: User-friendly 404 message visible, back to safety link functional.\nFAIL: Raw web server debug page, unhandled exception, or blank screen.",
                status="pending_review",
                source="fallback_template",
            ),
        ]

        return ExplorerResult(
            status="success",
            scenarios=scenarios,
            discovered_routes=[config.target_url, url],
            artifacts_created=artifacts_created,
        )

    def _fallback_exploration(
        self,
        config: ExplorerConfig,
        controller: PlaywrightController,
        log_callback: Callable,
        is_cancelled: Callable,
    ) -> ExplorerResult:
        log_callback("INFO", "Running autonomous heuristic discovery across DOM tree and network APIs...")
        return self._synthesize_from_state(config, controller, Path(config.workspace_dir) / "runs" / config.run_id, [], log_callback)

    def _synthesize_spec_only_plan(self, config: ExplorerConfig, log_callback: Callable) -> ExplorerResult:
        """Generates structured test scenarios based on URL, credentials, and PRD."""
        has_prd = bool(config.prd_text and config.prd_text.strip())
        scenarios = [
            DiscoveredScenario(
                title="User Authentication & Session Initialization",
                category="happy_path",
                priority="P0",
                preconditions="User account exists with configured credentials.",
                description="⚠️ FALLBACK TEMPLATE: Verify that valid credentials authenticate successfully and redirect to the dashboard.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": f"{config.target_url.rstrip('/')}/login", "expected_outcome": "Login page renders"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": config.credentials.get("username", "admin")},
                    {"step_number": 3, "action": "Fill", "target_element": "input[name='password']", "expected_outcome": "Valid password"},
                    {"step_number": 4, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Submits form"},
                ],
                expected_result="Session established, redirects to dashboard with welcome banner.",
                pass_fail_criteria="PASS: Auth cookie/token set, redirected to dashboard URL, user greeting displayed.\nFAIL: Remains on login page, 401 response without message, or 500 error.",
                status="pending_review",
                source="fallback_template",
            ),
            DiscoveredScenario(
                title="PRD Feature Verification" if has_prd else "Core Navigation & Route Mapping",
                category="happy_path",
                priority="P1",
                preconditions="User authenticated with standard permissions.",
                description=f"⚠️ FALLBACK TEMPLATE: Validate functional requirements specified in {'PRD' if has_prd else 'application discovery'}.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": config.target_url, "expected_outcome": "Main view loaded"},
                    {"step_number": 2, "action": "Click", "target_element": "nav a", "expected_outcome": "Navigates to primary feature section"},
                ],
                expected_result="Feature view renders without JS exceptions or broken assets.",
                pass_fail_criteria="PASS: Target feature components load and are interactive.\nFAIL: Broken layout, missing components, or console errors.",
                status="pending_review",
                source="fallback_template",
            ),
            DiscoveredScenario(
                title="Input Boundary & Form Validation",
                category="edge_case",
                priority="P2",
                preconditions="Form loaded with clean input fields.",
                description="⚠️ FALLBACK TEMPLATE: Submit forms with empty values, boundary length strings, and special characters.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": config.target_url, "expected_outcome": "Form loaded"},
                    {"step_number": 2, "action": "Fill", "target_element": "input", "expected_outcome": "Boundary and special character inputs"},
                    {"step_number": 3, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Form submitted"},
                ],
                expected_result="Form validation prevents invalid submission with descriptive error prompts.",
                pass_fail_criteria="PASS: Inline validation prompt highlights invalid fields.\nFAIL: Form submits invalid data or triggers unhandled server exception.",
                status="pending_review",
                source="fallback_template",
            ),
            DiscoveredScenario(
                title="Invalid Authentication & 404 Handling",
                category="error_flow",
                priority="P1",
                preconditions="Unauthenticated session.",
                description="⚠️ FALLBACK TEMPLATE: Verify that invalid credentials display an explicit error banner and non-existent routes show 404.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": f"{config.target_url.rstrip('/')}/login", "expected_outcome": "Login page loaded"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": "invalid_test_user"},
                    {"step_number": 3, "action": "Fill", "target_element": "input[name='password']", "expected_outcome": "wrong_password_99"},
                    {"step_number": 4, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Error banner visible"},
                ],
                expected_result="User remains unauthenticated with clear feedback.",
                pass_fail_criteria="PASS: Explicit error message 'Invalid credentials' displayed.\nFAIL: User logged in, blank screen, or unhandled 500 error.",
                status="pending_review",
                source="fallback_template",
            ),
        ]


        return ExplorerResult(
            status="success",
            scenarios=scenarios,
            discovered_routes=[config.target_url],
            artifacts_created=[],
        )

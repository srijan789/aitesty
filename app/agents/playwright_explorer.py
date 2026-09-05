import os
import re
import time
import json
import logging
import urllib.parse
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
            "name": "browser_scroll",
            "description": "Scroll the active browser window up or down to reveal dynamically loaded content, long tables, or footer links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["down", "up"], "description": "Scroll direction ('down' or 'up')."},
                    "amount": {"type": "integer", "description": "Pixels to scroll, e.g. 500.", "default": 500}
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_select",
            "description": "Select an option from an HTML <select> dropdown element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector for the select dropdown."},
                    "value": {"type": "string", "description": "Value attribute or text of the option to select."}
                },
                "required": ["selector", "value"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_links",
            "description": "Extract all discovered same-origin navigable URLs, buttons, and route paths found on the current page.",
            "parameters": {
                "type": "object",
                "properties": {}
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

    def _run_frontier_crawl(
        self,
        config: ExplorerConfig,
        controller: PlaywrightController,
        screenshots_dir: Path,
        artifacts_created: List[str],
        log_callback: Callable,
        is_cancelled: Callable,
    ) -> List[Dict[str, Any]]:
        """
        Systematically crawls the application using a frontier queue up to
        crawl_depth and max_pages. Collects routes, forms, inputs, and buttons.
        """
        crawl_depth = getattr(config, "crawl_depth", 2) or 2
        max_pages = getattr(config, "max_pages", 10) or 10
        parsed_target = urllib.parse.urlparse(config.target_url)
        allowed_host = parsed_target.hostname or ""

        log_callback("INFO", f"[Deep Crawler] Initiating frontier crawl (Depth Limit: {crawl_depth}, Max Routes: {max_pages}, Allowed Host: {allowed_host})")

        visited_canonicals = set()
        crawled_pages: List[Dict[str, Any]] = []
        queue: List[tuple] = [(config.target_url, 0)]
        step_counter = 0

        while queue and len(visited_canonicals) < max_pages:
            if is_cancelled():
                break

            current_url, depth = queue.pop(0)
            canonical = current_url.split("#")[0].rstrip("/")
            if canonical in visited_canonicals:
                continue

            visited_canonicals.add(canonical)
            step_counter += 1

            try:
                nav_res = controller.navigate(current_url)
                controller.wait(400)
                dom = controller.get_dom_summary()
                title = dom.get("title", "") or "View"
                dom_inner = dom.get("dom", {}) if isinstance(dom.get("dom"), dict) else {}
                forms = dom_inner.get("forms", [])
                buttons = dom_inner.get("buttons", [])
                inputs = dom_inner.get("inputs", [])
                headings = dom_inner.get("headings", [])

                # Take screenshot for the first 8 unique routes
                if step_counter <= 8:
                    path_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", urllib.parse.urlparse(current_url).path or "home").strip("_")[:20]
                    p = screenshots_dir / f"crawl_{step_counter}_{path_slug}.png"
                    try:
                        controller.take_screenshot(str(p))
                        artifacts_created.append(str(p))
                    except Exception:
                        pass

                page_info = {
                    "url": current_url,
                    "canonical": canonical,
                    "depth": depth,
                    "title": title,
                    "status": nav_res.get("status", 200),
                    "forms": forms,
                    "buttons": buttons,
                    "inputs": inputs,
                    "headings": headings,
                }
                crawled_pages.append(page_info)
                log_callback(
                    "INFO",
                    f"[Deep Crawler] Navigated to Route {len(visited_canonicals)}/{max_pages} [Depth {depth}]: {current_url} "
                    f"('{title}') - Found {len(forms)} form(s), {len(buttons)} button(s), {len(inputs)} input(s)"
                )

                # Discover child links if below depth limit
                if depth < crawl_depth:
                    targets = controller.extract_crawl_targets(allowed_host)
                    for t in targets:
                        target_url = t.get("url")
                        if not target_url:
                            continue
                        target_canonical = target_url.split("#")[0].rstrip("/")
                        if target_canonical not in visited_canonicals and not any(q[0].split("#")[0].rstrip("/") == target_canonical for q in queue):
                            queue.append((target_url, depth + 1))

            except Exception as e:
                log_callback("WARN", f"[Deep Crawler] Encountered issue navigating {current_url}: {e}")

        log_callback("INFO", f"[Deep Crawler] Frontier crawl completed: {len(crawled_pages)} route(s) mapped across depth {crawl_depth}.")
        return crawled_pages

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

        crawl_depth = getattr(config, "crawl_depth", 2) or 2
        max_pages = getattr(config, "max_pages", 10) or 10
        target_test_count = getattr(config, "target_test_count", 12) or 12
        exploration_strategy = getattr(config, "exploration_strategy", "balanced") or "balanced"

        log_callback("INFO", f"Launching Deep AI Explorer & Crawler for {config.target_url}")
        log_callback("INFO", f"Parameters: Crawl Depth={crawl_depth}, Max Pages={max_pages}, Target Tests={target_test_count}, Strategy={exploration_strategy}")
        log_callback("INFO", f"Model: {self.model} via TrueFoundry Gateway")

        has_prd = bool(config.prd_text and config.prd_text.strip())
        if has_prd:
            log_callback("INFO", "PRD document detected! Activating Specification-Driven Verification Mode.")
        else:
            log_callback("INFO", "No PRD provided. Activating Autonomous Multi-Route Discovery & Tour Mode.")

        client = self._get_client()
        workspace_path = Path(config.workspace_dir)
        runs_dir = workspace_path / "runs" / config.run_id
        screenshots_dir = runs_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)

        artifacts_created: List[str] = []

        # Start Playwright Browser Controller
        try:
            headless = getattr(config, "headless", True)
            slow_mo = getattr(config, "slow_mo", 500 if not headless else 0)
            with PlaywrightController(headless=headless, slow_mo=slow_mo) as controller:
                mode_label = "headless" if headless else f"headed (slow_mo: {slow_mo}ms)"
                log_callback("INFO", f"Chromium browser started [{mode_label}] with network sniffer & console listener attached.")

                # Phase 1: Deep Frontier Crawling & Route Mapping
                crawled_pages = self._run_frontier_crawl(
                    config=config,
                    controller=controller,
                    screenshots_dir=screenshots_dir,
                    artifacts_created=artifacts_created,
                    log_callback=log_callback,
                    is_cancelled=is_cancelled,
                )

                if is_cancelled():
                    return ExplorerResult(status="cancelled")

                discovered_routes = [p["url"] for p in crawled_pages] if crawled_pages else [config.target_url]
                if config.target_url not in discovered_routes:
                    discovered_routes.insert(0, config.target_url)

                # Phase 2: LLM Deep Probing & Synthesis
                system_prompt = self._build_system_prompt(config, has_prd, crawled_pages)
                messages = [{"role": "system", "content": system_prompt}]

                # Navigate back to primary target URL for active probing
                controller.navigate(config.target_url)
                dom_summary = controller.get_dom_summary()
                network_recent = controller.get_recent_network(limit=8)

                site_map_preview = "\n".join([
                    f"- Route {i+1}: {p['url']} ('{p['title']}') - {len(p.get('forms', []))} form(s), {len(p.get('buttons', []))} button(s)"
                    for i, p in enumerate(crawled_pages[:12])
                ])

                user_init_content = f"""Frontier Crawl Complete! Discovered {len(discovered_routes)} routes across the application:
{site_map_preview}

Current Browser State ({config.target_url}):
- Title: {dom_summary.get('title', 'N/A')}
- Recent Network Calls: {len(network_recent)} requests captured

MANDATORY GOAL:
You must probe interactive elements, test edge cases, and define a comprehensive QA test plan containing AT LEAST {target_test_count} distinct scenarios spanning the discovered routes.
When you have created >= {target_test_count} scenarios across Happy Paths, Edge Cases, and Error Flows, call finish_exploration."""

                messages.append({"role": "user", "content": user_init_content})

                # ReAct Tool-Calling Loop (Max 24 iterations for deep exploration)
                max_iterations = 24
                iteration = 0
                final_result: Optional[ExplorerResult] = None

                while iteration < max_iterations:
                    iteration += 1
                    if is_cancelled():
                        return ExplorerResult(status="cancelled")

                    # Turn limit warning
                    if iteration == max_iterations - 2:
                        log_callback("INFO", f"Approaching turn limit ({iteration}/{max_iterations}). Nudging agent to formulate scenarios and wrap up.")
                        messages.append({
                            "role": "user",
                            "content": f"You are approaching the exploration turn budget. Please call `finish_exploration` with at least {target_test_count} comprehensive scenarios covering the discovered routes now."
                        })

                    log_callback("INFO", f"[Agent Thinking] Turn {iteration}/{max_iterations} - Querying Gemini 3.7 Flash...")

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
                                log_callback("WARN", f"LLM Gateway unavailable: {llm_err}. Using autonomous deep crawler synthesis.")
                                return self._fallback_exploration(config, controller, crawled_pages, log_callback, is_cancelled)

                    message = response.choices[0].message
                    messages.append(message)

                    if message.content:
                        log_callback("INFO", f"[Agent Plan] {message.content.strip()[:300]}")

                    if not message.tool_calls:
                        log_callback("INFO", "No tool call generated. Prompting agent to continue exploration.")
                        messages.append({
                            "role": "user",
                            "content": f"Please continue navigating or define test cases. Remember: You must formulate at least {target_test_count} scenarios before calling finish_exploration."
                        })
                        continue

                    # Execute tool calls
                    finish_called = False
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

                        # Handle finish_exploration with Quota Enforcement
                        if fn_name == "finish_exploration":
                            finish_called = True
                            proposed_scenarios = fn_args.get("scenarios", [])
                            if isinstance(proposed_scenarios, str):
                                try:
                                    proposed_scenarios = json.loads(proposed_scenarios)
                                except Exception:
                                    proposed_scenarios = []

                            # If fewer than target_test_count scenarios, reject and enforce quota
                            if len(proposed_scenarios) < target_test_count and iteration < max_iterations - 2:
                                log_callback(
                                    "WARN",
                                    f"[Quota Guard] finish_exploration called with only {len(proposed_scenarios)}/{target_test_count} scenarios. Rejecting premature exit."
                                )
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": json.dumps({
                                        "error": f"Scenario quota not met: You defined {len(proposed_scenarios)} scenarios, but the target quota requires AT LEAST {target_test_count} scenarios across the discovered routes ({', '.join(discovered_routes[:6])}). Please expand your test scenarios across Happy Path, Edge Cases, and Error Flows before finishing."
                                    }),
                                })
                                break
                            else:
                                final_result = self._handle_finish(
                                    config=config,
                                    fn_args=fn_args,
                                    controller=controller,
                                    runs_dir=runs_dir,
                                    artifacts_created=artifacts_created,
                                    log_callback=log_callback,
                                    discovered_routes=discovered_routes,
                                    crawled_pages=crawled_pages,
                                )
                                break

                        # Execute browser tools
                        tool_output = self._execute_browser_tool(
                            fn_name=fn_name,
                            fn_args=fn_args,
                            controller=controller,
                            screenshots_dir=screenshots_dir,
                            artifacts_created=artifacts_created,
                            log_callback=log_callback,
                            config=config,
                        )
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_output),
                        })

                    if final_result:
                        break

                # If LLM reached turn limit or final_result has fewer than target_test_count scenarios
                if not final_result or len(final_result.scenarios) < target_test_count:
                    log_callback("INFO", f"[Deep Synthesis] Expanding test scenarios from crawled routes to fulfill target quota of {target_test_count}+...")
                    existing = final_result.scenarios if final_result else []
                    final_result = self._expand_and_synthesize_scenarios(
                        config=config,
                        controller=controller,
                        crawled_pages=crawled_pages,
                        existing_scenarios=existing,
                        runs_dir=runs_dir,
                        artifacts_created=artifacts_created,
                        log_callback=log_callback,
                    )

                # Dump network traffic
                network_dump_path = runs_dir / "network_traffic.json"
                controller.dump_network_traffic(str(network_dump_path))
                artifacts_created.append(str(network_dump_path))
                log_callback("INFO", f"Captured network traffic saved to runs/{config.run_id}/network_traffic.json")

                return final_result

        except Exception as browser_err:
            logger.exception(f"Playwright execution error: {browser_err}")
            log_callback("WARN", f"Browser context notice: {browser_err}. Generating comprehensive plan from target specification.")
            return self._synthesize_spec_only_plan(config, log_callback)

    def _build_system_prompt(self, config: ExplorerConfig, has_prd: bool, crawled_pages: List[Dict[str, Any]] = None) -> str:
        crawled_pages = crawled_pages or []
        crawl_depth = getattr(config, "crawl_depth", 2) or 2
        max_pages = getattr(config, "max_pages", 10) or 10
        target_test_count = getattr(config, "target_test_count", 12) or 12
        exploration_strategy = getattr(config, "exploration_strategy", "balanced") or "balanced"

        routes_text = ""
        if crawled_pages:
            routes_text = "\n".join([
                f"  * Route: {p['url']} [Title: '{p['title']}'] | Depth: {p.get('depth', 0)} | Forms: {len(p.get('forms', []))} | Buttons: {len(p.get('buttons', []))} | Inputs: {len(p.get('inputs', []))}"
                for p in crawled_pages[:15]
            ])
        else:
            routes_text = f"  * Route: {config.target_url}"

        base = f"""You are a Lead QA Engineer and Deep Exploratory Testing Specialist.
Your mission is to explore the target web application thoroughly across all its routes and interactive features, and synthesize a structured, exhaustive QA test plan.

APPLICATION CONFIGURATION:
- Base Target URL: {config.target_url}
- Authentication: {config.auth_type}
- Credentials: {json.dumps(config.credentials)}
- Scope / Directives: {config.scope_instructions or 'Full multi-route exploration'}
- Crawl Depth Limit: {crawl_depth} hops
- Exploration Strategy: {exploration_strategy}

DISCOVERED APPLICATION SITE MAP ({len(crawled_pages)} route(s) cataloged):
{routes_text}
"""
        if has_prd:
            base += f"""
=== PRODUCT REQUIREMENT DOCUMENT (PRD) ===
{config.prd_text}
==========================================
SPECIFICATION-DRIVEN EXPLORATORY TESTING:
1. Cross-reference PRD requirements and acceptance criteria against the running application.
2. Define scenarios verifying each user story across the discovered routes.
3. Verify primary workflows (Happy Paths), edge cases (boundary inputs, empty states, limits), and error flows.
"""
        else:
            base += """
AUTONOMOUS QA EXPLORATORY TOURS (MULTI-ROUTE):
1. Route & Feature Tour: Navigate menus, sub-routes, dashboards, and detail views discovered in the site map.
2. Input & Boundary Tour: Test forms with empty values, boundary lengths, and special characters.
3. Error Handling Tour: Observe network responses (HTTP 200 vs 4xx/5xx), route 404s, and auth rejections.
"""

        base += f"""
MANDATORY TEST SCENARIO QUOTA:
- You MUST define AT LEAST {target_test_count} comprehensive test cases. Generating only 3-4 tests is strictly prohibited.
- Spread your tests across ALL discovered routes.
- Required category balance:
  * Happy Path (~40-50%): Core flows, successful form submissions, navigation between views.
  * Edge Cases (~30%): Empty inputs, boundary lengths, special characters, rapid clicks, filtering.
  * Error Flows (~20-30%): Invalid routes (404), invalid inputs, unauthorized endpoints, network error recovery.

TEST CASE SCHEMA (Required for each scenario):
  * title: Clear, descriptive scenario name (e.g. 'Submit Project Creation Form With Valid Data')
  * category: 'happy_path' | 'edge_case' | 'error_flow'
  * priority: 'P0' (Critical blocker) | 'P1' (High) | 'P2' (Medium) | 'P3' (Low)
  * preconditions: State required before executing test (e.g. 'User authenticated on /projects/new')
  * description: What is being verified and why
  * steps: Array of numbered action steps with verbs, targets, and expected outcomes
  * expected_result: Overall intended outcome
  * pass_fail_criteria: Explicit checklist defining what constitutes a PASS vs a FAIL

When you have thoroughly explored the routes and prepared at least {target_test_count} scenarios, call `finish_exploration`.
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
        config: Optional[ExplorerConfig] = None,
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

            elif fn_name == "browser_select":
                selector = fn_args.get("selector", "")
                value = fn_args.get("value", "")
                return controller.select_option(selector, value)

            elif fn_name == "browser_scroll":
                direction = fn_args.get("direction", "down")
                amount = fn_args.get("amount", 500)
                return controller.scroll(direction=direction, amount=amount)

            elif fn_name == "browser_get_links":
                target = config.target_url if config else controller.page.url
                host = urllib.parse.urlparse(target).hostname or ""
                return {"discovered_links": controller.extract_crawl_targets(host)}

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
            logger.warning(f"Tool {fn_name} execution error: {tool_err}", exc_info=True)
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
        discovered_routes: Optional[List[str]] = None,
        crawled_pages: Optional[List[Dict[str, Any]]] = None,
    ) -> ExplorerResult:
        if isinstance(fn_args, str):
            try:
                fn_args = json.loads(fn_args)
            except Exception:
                fn_args = {}

        summary = fn_args.get("summary", "QA exploration completed successfully.")
        routes = discovered_routes or fn_args.get("discovered_routes", [config.target_url])
        if isinstance(routes, str):
            try:
                routes = json.loads(routes)
            except Exception:
                routes = [routes]
        if not isinstance(routes, list):
            routes = [str(routes)]

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

        target_test_count = getattr(config, "target_test_count", 12) or 12
        if len(scenarios) < target_test_count and crawled_pages:
            log_callback("INFO", f"Synthesizing additional scenarios across crawled routes to reach target quota ({len(scenarios)} -> {target_test_count}+)...")
            return self._expand_and_synthesize_scenarios(
                config=config,
                controller=controller,
                crawled_pages=crawled_pages,
                existing_scenarios=scenarios,
                runs_dir=runs_dir,
                artifacts_created=artifacts_created,
                log_callback=log_callback,
            )

        log_callback("INFO", f"QA Plan synthesized: {len(scenarios)} test cases defined across categories (marked for review).")

        return ExplorerResult(
            status="success",
            scenarios=scenarios,
            discovered_routes=routes,
            artifacts_created=artifacts_created,
        )

    def _expand_and_synthesize_scenarios(
        self,
        config: ExplorerConfig,
        controller: PlaywrightController,
        crawled_pages: List[Dict[str, Any]],
        existing_scenarios: List[DiscoveredScenario],
        runs_dir: Path,
        artifacts_created: List[str],
        log_callback: Callable,
    ) -> ExplorerResult:
        """
        Dynamically synthesizes comprehensive QA test scenarios across all crawled routes,
        detected forms, interactive elements, auth state, and PRD specifications to guarantee
        that the target scenario quota (e.g. 12-25+ tests) is thoroughly fulfilled.
        """
        target_count = getattr(config, "target_test_count", 12) or 12
        scenarios: List[DiscoveredScenario] = list(existing_scenarios)
        existing_titles = {s.title.lower() for s in scenarios}
        discovered_routes = [p["url"] for p in crawled_pages] if crawled_pages else [config.target_url]
        if config.target_url not in discovered_routes:
            discovered_routes.insert(0, config.target_url)

        def add_scenario(s: DiscoveredScenario):
            if s.title.lower() not in existing_titles:
                scenarios.append(s)
                existing_titles.add(s.title.lower())

        # 1. Authentication Scenarios (if configured)
        has_auth = config.auth_type and config.auth_type != "none"
        if has_auth or config.credentials:
            username = config.credentials.get("username") or "qa_test_user"
            login_url = f"{config.target_url.rstrip('/')}/login"

            add_scenario(DiscoveredScenario(
                title="User Authentication & Session Credential Verification",
                category="happy_path",
                priority="P0",
                preconditions=f"Account exists with valid credentials: '{username}'.",
                description="Verify that an authorized user can submit valid credentials and successfully establish an authenticated session.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": login_url, "expected_outcome": "Login view renders with input fields"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='username'], input[type='email']", "expected_outcome": f"Entered {username}"},
                    {"step_number": 3, "action": "Fill", "target_element": "input[name='password'], input[type='password']", "expected_outcome": "Entered valid password"},
                    {"step_number": 4, "action": "Click", "target_element": "button[type='submit'], input[type='submit']", "expected_outcome": "Credentials submitted"},
                    {"step_number": 5, "action": "Assert", "target_element": "body", "expected_outcome": "Redirected to dashboard/home, session cookie or token established"},
                ],
                expected_result="User session successfully created; application redirects to authenticated workspace.",
                pass_fail_criteria="PASS: HTTP 200/302 response, auth cookie/token set, landing banner visible.\nFAIL: Remains on login page with error, or 500 server exception.",
                status="pending_review",
                source="crawler_synthesis",
            ))

            add_scenario(DiscoveredScenario(
                title="Invalid Authentication Credentials Rejection",
                category="error_flow",
                priority="P1",
                preconditions="Standard unauthenticated user session.",
                description="Verify that invalid username/password submissions trigger an explicit error banner and prevent unauthorized access.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": login_url, "expected_outcome": "Login form rendered"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": "invalid_qa_user_999"},
                    {"step_number": 3, "action": "Fill", "target_element": "input[name='password']", "expected_outcome": "IncorrectPassword!@#"},
                    {"step_number": 4, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Form submitted"},
                    {"step_number": 5, "action": "Assert", "target_element": ".alert, [role='alert'], .error", "expected_outcome": "Explicit error message 'Invalid credentials' displayed"},
                ],
                expected_result="Authentication is denied; descriptive error message is presented; user remains logged out.",
                pass_fail_criteria="PASS: Clear error banner visible, user cannot access protected views.\nFAIL: Silent reload, blank screen, or authenticated unexpectedly.",
                status="pending_review",
                source="crawler_synthesis",
            ))

        # 2. PRD Specification Scenarios (if PRD text is provided)
        if config.prd_text and config.prd_text.strip():
            lines = [line.strip().lstrip("-*0123456789. ") for line in config.prd_text.splitlines() if len(line.strip()) > 15]
            for idx, req_line in enumerate(lines[:5], 1):
                clean_req = req_line[:60]
                add_scenario(DiscoveredScenario(
                    title=f"PRD Requirement Verification: {clean_req}",
                    category="happy_path" if idx % 3 != 0 else "edge_case",
                    priority="P1",
                    preconditions=f"Application loaded at {config.target_url} matching PRD specification state.",
                    description=f"Validate that the application fulfills the acceptance criteria specified in the PRD: '{req_line}'.",
                    steps=[
                        {"step_number": 1, "action": "Navigate", "target_element": config.target_url, "expected_outcome": "Target view renders"},
                        {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": f"Feature components corresponding to '{clean_req}' are present"},
                        {"step_number": 3, "action": "Click", "target_element": "interactive element", "expected_outcome": "Expected workflow initiates without error"},
                    ],
                    expected_result=f"System satisfies PRD criteria for '{clean_req}'.",
                    pass_fail_criteria=f"PASS: Acceptance criteria for '{clean_req}' fully satisfied without error.\nFAIL: Feature missing, incorrect output, or unhandled exception.",
                    status="pending_review",
                    source="crawler_synthesis",
                ))

        # 3. Route-Specific Scenarios for each Crawled Page
        pages_to_process = crawled_pages if crawled_pages else [{"url": config.target_url, "title": "Home", "forms": [], "buttons": [], "inputs": []}]
        for idx, page in enumerate(pages_to_process, 1):
            url = page["url"]
            title = page.get("title") or f"Route {idx}"
            parsed = urllib.parse.urlparse(url)
            route_path = parsed.path or "/"
            route_slug = route_path.replace("/", " ").strip().title() or "Home"

            # 3A. Route Navigation & Layout Render (Happy Path)
            add_scenario(DiscoveredScenario(
                title=f"Route Navigation & Layout Render: {route_slug} ({route_path})",
                category="happy_path",
                priority="P1" if idx > 1 else "P0",
                preconditions=f"Network connectivity active; navigating to {url}.",
                description=f"Verify that navigating to '{route_path}' successfully returns HTTP 200 and renders key components without script crashes.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": url, "expected_outcome": "HTTP 200 response with DOM ready"},
                    {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": f"View header and layout matching '{title}' loaded"},
                    {"step_number": 3, "action": "Assert", "target_element": "nav, header, main", "expected_outcome": "Core navigation and content containers present"},
                ],
                expected_result=f"Page loads within SLA; DOM structure renders intact for '{route_slug}'.",
                pass_fail_criteria="PASS: HTTP 200, page renders, zero fatal uncaught console errors.\nFAIL: White screen, 404/500 error, or broken assets.",
                status="pending_review",
                source="crawler_synthesis",
            ))

            # 3B. Form Submission & Input Validation (if forms exist)
            forms = page.get("forms", [])
            inputs = page.get("inputs", [])
            if forms or inputs:
                form_selector = "form"
                add_scenario(DiscoveredScenario(
                    title=f"Form Submission & Field Processing: {route_slug}",
                    category="happy_path",
                    priority="P1",
                    preconditions=f"Navigate to {url} with interactive form loaded.",
                    description=f"Verify that submitting the primary form on '{route_path}' with populated fields executes the intended workflow.",
                    steps=[
                        {"step_number": 1, "action": "Navigate", "target_element": url, "expected_outcome": "Form visible"},
                        {"step_number": 2, "action": "Fill", "target_element": "input:not([type='hidden'])", "expected_outcome": "Enter valid test data"},
                        {"step_number": 3, "action": "Click", "target_element": "button[type='submit'], input[type='submit']", "expected_outcome": "Form submitted"},
                        {"step_number": 4, "action": "Assert", "target_element": "body", "expected_outcome": "Success feedback displayed or state transition completed"},
                    ],
                    expected_result="Form processes submission gracefully with appropriate state feedback.",
                    pass_fail_criteria="PASS: Data accepted, success toast/redirect rendered, HTTP 200/201/302.\nFAIL: Form frozen, 500 error, or validation failure on valid data.",
                    status="pending_review",
                    source="crawler_synthesis",
                ))

                add_scenario(DiscoveredScenario(
                    title=f"Input Boundary & Empty Field Validation: {route_slug}",
                    category="edge_case",
                    priority="P2",
                    preconditions=f"Navigate to {url} with empty form inputs.",
                    description=f"Probe input fields on '{route_path}' with boundary-length strings (255+ chars), special characters, and empty required fields.",
                    steps=[
                        {"step_number": 1, "action": "Navigate", "target_element": url, "expected_outcome": "Form displayed"},
                        {"step_number": 2, "action": "Fill", "target_element": "input:not([type='hidden'])", "expected_outcome": "Enter special characters: <script>alert(1)</script> & 255+ chars"},
                        {"step_number": 3, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Submit triggered"},
                        {"step_number": 4, "action": "Assert", "target_element": ".error, :invalid, .alert", "expected_outcome": "Client-side or server validation message displayed"},
                    ],
                    expected_result="Application sanitizes inputs and blocks malformed data with clear validation prompts.",
                    pass_fail_criteria="PASS: Input sanitized, descriptive validation prompt shown, no server 500.\nFAIL: XSS executed, database syntax leak, or unhandled 500 crash.",
                    status="pending_review",
                    source="crawler_synthesis",
                ))

            # 3C. Buttons / Interactive Affordance Probing
            buttons = page.get("buttons", [])
            if buttons and len(buttons) > 1:
                btn_name = buttons[0].get("text", "Primary Action")[:25]
                add_scenario(DiscoveredScenario(
                    title=f"Interactive Control & Action Trigger: {btn_name} ({route_slug})",
                    category="edge_case",
                    priority="P2",
                    preconditions=f"Target page loaded at {url}.",
                    description=f"Verify UI responsiveness and rapid interaction handling on '{btn_name}' within '{route_path}'.",
                    steps=[
                        {"step_number": 1, "action": "Navigate", "target_element": url, "expected_outcome": "View interactive"},
                        {"step_number": 2, "action": "Click", "target_element": "button, a.btn", "expected_outcome": f"Trigger '{btn_name}'"},
                        {"step_number": 3, "action": "Assert", "target_element": "body", "expected_outcome": "UI state updates or modal/dialog displays properly"},
                    ],
                    expected_result="Interactive control handles user event without visual corruption or console errors.",
                    pass_fail_criteria="PASS: State changes as expected, no broken layouts.\nFAIL: Unresponsive button, infinite spinner, or uncaught exception.",
                    status="pending_review",
                    source="crawler_synthesis",
                ))

            # 3D. Route Error Handling (Error Flow)
            add_scenario(DiscoveredScenario(
                title=f"Non-Existent Sub-Route 404 Handling ({route_slug})",
                category="error_flow",
                priority="P2",
                preconditions="Standard unauthenticated session.",
                description=f"Verify graceful 404 error page handling when requesting an invalid sub-route under '{route_path}'.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": f"{url.rstrip('/')}/qa-nonexistent-subroute-404", "expected_outcome": "Request sent"},
                    {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": "User-friendly 404 page rendered with link to return home"},
                ],
                expected_result="Custom 404 error page displayed; no stack traces exposed.",
                pass_fail_criteria="PASS: Clean 404 message, navigation to safety available.\nFAIL: Raw server debug trace, unhandled crash, or blank screen.",
                status="pending_review",
                source="crawler_synthesis",
            ))

        # 4. Cross-Cutting System Edge Cases to fulfill quota if still needed
        supplemental_tests = [
            DiscoveredScenario(
                title="Rapid Action & Double-Click Idempotency Probing",
                category="edge_case",
                priority="P2",
                preconditions=f"Application loaded at {config.target_url}.",
                description="Verify that rapid successive clicks on action triggers do not duplicate submissions or create race conditions.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": config.target_url, "expected_outcome": "Page ready"},
                    {"step_number": 2, "action": "Click", "target_element": "button, a", "expected_outcome": "First click initiates action"},
                    {"step_number": 3, "action": "Click", "target_element": "button, a", "expected_outcome": "Rapid second click is debounced/ignored"},
                    {"step_number": 4, "action": "Assert", "target_element": "body", "expected_outcome": "Only single state transaction processed"},
                ],
                expected_result="Application debounces rapid input without duplicate records or error states.",
                pass_fail_criteria="PASS: Idempotent behavior observed, button disabled during pending state.\nFAIL: Duplicate database records or crash.",
                status="pending_review",
                source="crawler_synthesis",
            ),
            DiscoveredScenario(
                title="Responsive Viewport Breakpoint & Layout Stability",
                category="edge_case",
                priority="P2",
                preconditions="Target application loaded in responsive viewport.",
                description="Verify that application layout renders correctly under mobile/tablet viewports (375x812) without horizontal overflow.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": config.target_url, "expected_outcome": "Mobile viewport rendered"},
                    {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": "Navigation collapses to hamburger/drawer menu"},
                    {"step_number": 3, "action": "Assert", "target_element": "main, .container", "expected_outcome": "Zero horizontal scrollbar; cards and text wrap gracefully"},
                ],
                expected_result="Layout is responsive, mobile menu is functional, no clipped content.",
                pass_fail_criteria="PASS: Mobile layout intact, text legible, no clipped interactive elements.\nFAIL: Broken layout, overlapping text, or unusable controls.",
                status="pending_review",
                source="crawler_synthesis",
            ),
            DiscoveredScenario(
                title="Network Interruption & Slow Connection Degradation",
                category="error_flow",
                priority="P2",
                preconditions="Network throttling active.",
                description="Verify application behavior when API network responses are delayed or encounter intermittent disconnection.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": config.target_url, "expected_outcome": "Application starts loading"},
                    {"step_number": 2, "action": "Assert", "target_element": ".loading, .spinner, body", "expected_outcome": "Appropriate skeleton loader or spinner displayed"},
                    {"step_number": 3, "action": "Assert", "target_element": "body", "expected_outcome": "Clean retry prompt if network request fails"},
                ],
                expected_result="Loading state informs user; network errors display friendly retry option.",
                pass_fail_criteria="PASS: User receives loading indicator and graceful retry prompt.\nFAIL: Silent freeze or unhandled JavaScript promise rejection.",
                status="pending_review",
                source="crawler_synthesis",
            ),
            DiscoveredScenario(
                title="Security & Unauthorized Resource Access Guard",
                category="error_flow",
                priority="P1",
                preconditions="Unauthenticated session.",
                description="Verify that direct URL access to administrative and protected endpoints redirects to login or returns 403 Forbidden.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": f"{config.target_url.rstrip('/')}/admin", "expected_outcome": "Protected route requested"},
                    {"step_number": 2, "action": "Assert", "target_element": "body", "expected_outcome": "Redirected to /login or custom 403 Access Denied page"},
                ],
                expected_result="Unauthorized users cannot access protected administrative views.",
                pass_fail_criteria="PASS: Access blocked, redirected to login or 403 error page.\nFAIL: Protected data visible without authentication.",
                status="pending_review",
                source="crawler_synthesis",
            ),
        ]

        for supp in supplemental_tests:
            if len(scenarios) >= target_count:
                break
            add_scenario(supp)

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
        """Synthesizes structured QA test scenarios from observed DOM & crawler state."""
        dom = controller.get_dom_summary()
        url = controller.page.url if controller.page else config.target_url
        title = dom.get("title", "Application")
        forms = dom.get("dom", {}).get("forms", []) if isinstance(dom.get("dom"), dict) else []
        buttons = dom.get("dom", {}).get("buttons", []) if isinstance(dom.get("dom"), dict) else []
        inputs = dom.get("dom", {}).get("inputs", []) if isinstance(dom.get("dom"), dict) else []

        page_info = [{"url": url, "title": title, "forms": forms, "buttons": buttons, "inputs": inputs}]
        return self._expand_and_synthesize_scenarios(
            config=config,
            controller=controller,
            crawled_pages=page_info,
            existing_scenarios=[],
            runs_dir=runs_dir,
            artifacts_created=artifacts_created,
            log_callback=log_callback,
        )

    def _fallback_exploration(
        self,
        config: ExplorerConfig,
        controller: PlaywrightController,
        crawled_pages: List[Dict[str, Any]],
        log_callback: Callable,
        is_cancelled: Callable,
    ) -> ExplorerResult:
        log_callback("INFO", f"Synthesizing high-coverage QA test scenarios across {len(crawled_pages)} crawled routes...")
        runs_dir = Path(config.workspace_dir) / "runs" / config.run_id
        return self._expand_and_synthesize_scenarios(
            config=config,
            controller=controller,
            crawled_pages=crawled_pages,
            existing_scenarios=[],
            runs_dir=runs_dir,
            artifacts_created=[],
            log_callback=log_callback,
        )

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



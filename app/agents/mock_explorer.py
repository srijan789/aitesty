import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from app.agents.base import (
    BaseExplorerAgent,
    ExplorerConfig,
    ExplorerResult,
    DiscoveredScenario,
    ScenarioStep,
)

class MockExplorerAgent(BaseExplorerAgent):
    """
    Stage 1 Mock Explorer Agent.
    Simulates autonomous browser discovery, authentication checks,
    route mapping, scenario generation, and initial Playwright test skeleton writing.
    """

    def explore(
        self,
        config: ExplorerConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ExplorerResult:
        def check_cancelled():
            if cancel_check and cancel_check():
                log_callback("WARN", "Exploration cancelled by user request.", None)
                return True
            return False

        log_callback("INFO", f"Initializing Explorer Agent for target: {config.target_url}", {"url": config.target_url})
        time.sleep(0.4)
        if check_cancelled():
            return ExplorerResult(status="cancelled")

        # Step 1: Headless browser boot
        log_callback("INFO", "Launching headless Chromium browser instance...", {"browser": "chromium", "viewport": "1920x1080"})
        time.sleep(0.4)
        if check_cancelled():
            return ExplorerResult(status="cancelled")

        # Step 2: Navigate to target URL
        log_callback("INFO", f"Navigating to {config.target_url} (HTTP GET)", {"status": "navigating"})
        time.sleep(0.5)
        if check_cancelled():
            return ExplorerResult(status="cancelled")
        log_callback("INFO", "Target application loaded. DOM Content Loaded in 342ms. Status: 200 OK", {"dom_ready_ms": 342})

        # Step 3: Auth inspection & form filling
        if config.auth_type != "none":
            log_callback("INFO", f"Detected {config.auth_type.upper()} authentication required. Scanning for login inputs...", None)
            time.sleep(0.4)
            if check_cancelled():
                return ExplorerResult(status="cancelled")

            username = config.credentials.get("username", "admin")
            log_callback("INFO", f"Found input[name='username'] and input[type='password']. Submitting credentials for '{username}'...", None)
            time.sleep(0.5)
            if check_cancelled():
                return ExplorerResult(status="cancelled")

            log_callback("INFO", "Authentication successful. Session cookie established.", {"session": "active"})
        else:
            log_callback("INFO", "No authentication configured. Proceeding with public page exploration.", None)

        time.sleep(0.3)
        if check_cancelled():
            return ExplorerResult(status="cancelled")

        # Step 4: Route discovery & DOM mapping
        discovered_routes = [
            f"{config.target_url.rstrip('/')}/",
            f"{config.target_url.rstrip('/')}/dashboard",
            f"{config.target_url.rstrip('/')}/settings",
            f"{config.target_url.rstrip('/')}/users",
        ]
        log_callback("INFO", f"Discovered {len(discovered_routes)} navigation routes across application DOM.", {"routes": discovered_routes})
        time.sleep(0.4)
        if check_cancelled():
            return ExplorerResult(status="cancelled")

        # Step 5: Test scenario synthesis
        log_callback("INFO", "Synthesizing test scenarios from interaction graph...", None)
        time.sleep(0.4)
        if check_cancelled():
            return ExplorerResult(status="cancelled")

        scenarios = [
            DiscoveredScenario(
                title="User Authentication & Dashboard Redirect",
                category="happy_path",
                description="Verify that a valid user can log in and is redirected to the main dashboard.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": "/login", "expected_outcome": "Login form displays"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": "Username populated"},
                    {"step_number": 3, "action": "Fill", "target_element": "input[name='password']", "expected_outcome": "Password masked"},
                    {"step_number": 4, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Form submitted"},
                    {"step_number": 5, "action": "Assert", "target_element": "h1.dashboard-title", "expected_outcome": "Dashboard renders successfully"},
                ],
                expected_result="User session created, HTTP 200 on /dashboard, greeting header visible.",
                suggested_spec_filename="tests/test_auth_flow.spec.py",
            ),
            DiscoveredScenario(
                title="Navigation Menu Routing",
                category="happy_path",
                description="Ensure all top-level sidebar navigation links load their corresponding view without uncaught console errors.",
                steps=[
                    {"step_number": 1, "action": "Click", "target_element": "a[href='/users']", "expected_outcome": "Navigates to Users table"},
                    {"step_number": 2, "action": "Assert", "target_element": "table.user-list", "expected_outcome": "User list visible"},
                    {"step_number": 3, "action": "Click", "target_element": "a[href='/settings']", "expected_outcome": "Navigates to Settings page"},
                    {"step_number": 4, "action": "Assert", "target_element": "form#settings-form", "expected_outcome": "Settings form visible"},
                ],
                expected_result="All views render with HTTP 200 and zero JS console exceptions.",
                suggested_spec_filename="tests/test_navigation.spec.py",
            ),
            DiscoveredScenario(
                title="Form Input Boundary & Special Characters",
                category="edge_case",
                description="Submit text inputs with boundary lengths (255+ chars) and Unicode / emojis.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": "/settings", "expected_outcome": "Settings page loaded"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='display_name']", "expected_outcome": "String with 500 chars and emojis 🚀"},
                    {"step_number": 3, "action": "Click", "target_element": "button#save", "expected_outcome": "Validation triggered or sanitized"},
                ],
                expected_result="Input is either accepted safely or graceful client validation prevents crash.",
                suggested_spec_filename="tests/test_edge_cases.spec.py",
            ),
            DiscoveredScenario(
                title="Invalid Credentials Rejection",
                category="error_flow",
                description="Attempt login with wrong password and assert that an explicit error banner appears without crash.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": "/login", "expected_outcome": "Login form rendered"},
                    {"step_number": 2, "action": "Fill", "target_element": "input[name='username']", "expected_outcome": "valid_user"},
                    {"step_number": 3, "action": "Fill", "target_element": "input[name='password']", "expected_outcome": "wrong_password_999"},
                    {"step_number": 4, "action": "Click", "target_element": "button[type='submit']", "expected_outcome": "Form submitted"},
                    {"step_number": 5, "action": "Assert", "target_element": ".alert-danger", "expected_outcome": "Invalid credentials banner shown"},
                ],
                expected_result="User remains on /login with HTTP 401 or user-friendly error message.",
                suggested_spec_filename="tests/test_error_handling.spec.py",
            ),
            DiscoveredScenario(
                title="404 Page Not Found Handling",
                category="error_flow",
                description="Navigate to an invalid non-existent URL route and assert custom 404 page.",
                steps=[
                    {"step_number": 1, "action": "Navigate", "target_element": "/non-existent-random-route-99", "expected_outcome": "Page requested"},
                    {"step_number": 2, "action": "Assert", "target_element": "h1", "expected_outcome": "Contains 'Page Not Found' or 404 banner"},
                ],
                expected_result="Clean 404 response without exposing raw stack traces or internal server error.",
                suggested_spec_filename="tests/test_error_handling.spec.py",
            ),
        ]

        # Step 6: Generate Playwright test script in workspace
        tests_dir = Path(config.workspace_dir) / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        sample_spec_path = tests_dir / "test_auth_flow.spec.py"
        
        spec_content = f'''"""
Autonomous Generated Playwright Test Suite for {config.target_url}
Generated by Aitesty Autonomous Explorer
"""
import pytest
from playwright.sync_api import Page, expect

TARGET_URL = "{config.target_url}"

def test_user_authentication_flow(page: Page):
    """Scenario: User Authentication & Dashboard Redirect"""
    page.goto(f"{{TARGET_URL}}/login")
    
    # Fill login form
    if page.locator("input[name='username']").is_visible():
        page.fill("input[name='username']", "{config.credentials.get('username', 'admin')}")
        page.fill("input[name='password']", "secret_pass")
        page.click("button[type='submit']")
        
        # Verify dashboard redirect
        expect(page).to_have_url(f"{{TARGET_URL}}/dashboard")
    else:
        # If public page without login form, ensure home renders
        page.goto(TARGET_URL)
        expect(page).to_have_title(lambda t: len(t) > 0)

def test_invalid_login_shows_error(page: Page):
    """Scenario: Invalid Credentials Rejection"""
    page.goto(f"{{TARGET_URL}}/login")
    if page.locator("input[name='username']").is_visible():
        page.fill("input[name='username']", "invalid_user")
        page.fill("input[name='password']", "invalid_password")
        page.click("button[type='submit']")
        
        # Expect error message
        error_locator = page.locator(".alert, .error-message, [role='alert']")
        expect(error_locator).to_be_visible()
'''
        with open(sample_spec_path, "w", encoding="utf-8") as f:
            f.write(spec_content)

        artifacts_created = [str(sample_spec_path)]
        log_callback("INFO", f"Generated Playwright test script: tests/test_auth_flow.spec.py", {"file": "tests/test_auth_flow.spec.py"})
        time.sleep(0.3)

        log_callback("INFO", f"Exploration complete. Synthesized {len(scenarios)} test scenarios across 3 categories.", {
            "total_scenarios": len(scenarios),
            "happy_path": sum(1 for s in scenarios if s.category == "happy_path"),
            "edge_case": sum(1 for s in scenarios if s.category == "edge_case"),
            "error_flow": sum(1 for s in scenarios if s.category == "error_flow"),
        })

        return ExplorerResult(
            status="success",
            scenarios=scenarios,
            discovered_routes=discovered_routes,
            artifacts_created=artifacts_created,
        )

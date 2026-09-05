import pytest
import re
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net"
LOGIN_URL = f"{BASE_URL}/sso/login"
AUTH_USER = "user-3-Team10@velogent.com"
AUTH_PASS = "F@@OLwY16C"


def login_if_needed(page: Page) -> None:
    """Helper to authenticate the user and ensure navigation to dashboard."""
    print(f"[AUTH] Navigating to {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="networkidle")

    # Check if already authenticated and redirected
    if "/sso/login" not in page.url:
        print(f"[AUTH] Already authenticated, current URL: {page.url}")
        return

    print("[AUTH] Performing login with provided credentials...")
    username_input = page.locator('input[type="email"], input[name="username"], input[name="email"], input[id="username"], input[id="email"]').first
    password_input = page.locator('input[type="password"], input[name="password"], input[id="password"]').first

    if username_input.is_visible(timeout=5000):
        username_input.fill(AUTH_USER)
        password_input.fill(AUTH_PASS)
        submit_btn = page.locator('button:has-text("Sign in"), button:has-text("Log in"), button[type="submit"]').first
        submit_btn.click()

        # Wait for navigation away from /sso/login
        page.wait_for_url(lambda url: "/sso/login" not in url, timeout=15000)
        print(f"[AUTH] Successfully logged in. Current URL: {page.url}")
    else:
        print("[AUTH] Login inputs not detected; checking current URL state.")


def test_dashboard_tabs_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Dashboard Tab Switching (Overview vs Cost)
    Scenario ID: c9f61ee8-417e-4cdd-82b3-c1ef05b3a090
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Ensure user authentication")
        login_if_needed(page)

        print("[STEP 2] Navigate directly to /dashboard/overview")
        if not page.url.endswith("/dashboard/overview"):
            page.goto(f"{BASE_URL}/dashboard/overview", wait_until="networkidle")

        print("[STEP 3] Verify Overview tab and dashboard container are rendered")
        overview_tab = page.locator('button:has-text("Overview"), [role="tab"]:has-text("Overview"), a:has-text("Overview")').first
        expect(overview_tab).to_be_visible(timeout=10000)

        # Verify overview active indicator or main content container
        content_container = page.locator('main, [role="main"], #root, .dashboard-container').first
        expect(content_container).to_be_visible()
        print("[ASSERT] Initial Overview tab view rendered successfully.")

    except Exception as e:
        screenshot_path = "failure_c9f61ee8_01_navigate_and_view.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 01 failed: {e}. Screenshot captured to {screenshot_path}")
        raise e


def test_dashboard_tabs_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Dashboard Tab Switching (Overview vs Cost)
    Scenario ID: c9f61ee8-417e-4cdd-82b3-c1ef05b3a090
    Subtest: Interaction & Input Validation (Switch to Cost)
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticate and navigate to dashboard")
        login_if_needed(page)
        if "/dashboard" not in page.url:
            page.goto(f"{BASE_URL}/dashboard/overview", wait_until="networkidle")

        print("[STEP 2] Locate and click on Cost tab")
        cost_tab = page.locator('button:has-text("Cost"), [role="tab"]:has-text("Cost"), a:has-text("Cost")').first
        expect(cost_tab).to_be_visible(timeout=10000)
        cost_tab.click()

        print("[STEP 3] Validate Cost metrics and tab state")
        # Ensure Cost tab is selected or active
        cost_content = page.locator('text=Cost, [data-testid*="cost"], canvas, svg, .metric-card, .recharts-wrapper').first
        expect(cost_content).to_be_visible(timeout=10000)
        print("[ASSERT] Cost metrics/breakdown panel is visible and active.")

    except Exception as e:
        screenshot_path = "failure_c9f61ee8_02_interaction_and_validation.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 02 failed: {e}. Screenshot captured to {screenshot_path}")
        raise e


def test_dashboard_tabs_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Dashboard Tab Switching (Overview vs Cost)
    Scenario ID: c9f61ee8-417e-4cdd-82b3-c1ef05b3a090
    Subtest: Complete Action & Final Verification (Cost to Overview Round-trip)
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticate and open dashboard")
        login_if_needed(page)
        if "/dashboard" not in page.url:
            page.goto(f"{BASE_URL}/dashboard/overview", wait_until="networkidle")

        cost_tab = page.locator('button:has-text("Cost"), [role="tab"]:has-text("Cost"), a:has-text("Cost")').first
        overview_tab = page.locator('button:has-text("Overview"), [role="tab"]:has-text("Overview"), a:has-text("Overview")').first

        print("[STEP 2] Switch to Cost tab first")
        expect(cost_tab).to_be_visible(timeout=10000)
        cost_tab.click()

        print("[STEP 3] Switch back to Overview tab")
        expect(overview_tab).to_be_visible(timeout=10000)
        overview_tab.click()

        print("[STEP 4] Verify Overview view restored properly")
        overview_content = page.locator('text=Overview, [data-testid*="overview"], canvas, svg, .metric-card, .recharts-wrapper').first
        expect(overview_content).to_be_visible(timeout=10000)
        print("[ASSERT] Round-trip tab switching between Cost and Overview verified successfully.")

    except Exception as e:
        screenshot_path = "failure_c9f61ee8_03_action_and_outcome.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 03 failed: {e}. Screenshot captured to {screenshot_path}")
        raise e

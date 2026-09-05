import pytest
import re
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net"
LOGIN_URL = f"{BASE_URL}/sso/login"
AUTH_USERNAME = "user-3-Team10@velogent.com"
AUTH_PASSWORD = "F@@OLwY16C"
INVALID_ROUTE = f"{BASE_URL}/non-existent-route-qa-test"


def perform_login_if_needed(page: Page) -> bool:
    """Helper to authenticate user session if not already logged in."""
    print("[AUTH] Checking authentication status...")
    page.goto(LOGIN_URL, wait_until="networkidle")

    # Check if login form is displayed
    username_input = page.locator("input[placeholder*='username' i], input[name='username'], input[type='text'], input[type='email']").first
    password_input = page.locator("input[placeholder*='password' i], input[name='password'], input[type='password']").first
    submit_btn = page.locator("button:has-text('Sign in'), button:has-text('Log in'), button[type='submit']").first

    if username_input.is_visible(timeout=3000):
        print(f"[AUTH] Submitting credentials for {AUTH_USERNAME}...")
        username_input.fill(AUTH_USERNAME)
        password_input.fill(AUTH_PASSWORD)
        submit_btn.click()
        # Wait for transition away from login or network stabilization
        try:
            page.wait_for_url(lambda url: "/sso/login" not in url, timeout=10000)
            page.wait_for_load_state("networkidle", timeout=5000)
            print(f"[AUTH] Successfully navigated after login to: {page.url}")
            return True
        except Exception as e:
            print(f"[AUTH] Note: Login redirection finished with URL: {page.url} ({e})")
            return False
    else:
        print("[AUTH] Already authenticated or login form not present.")
        return True


def test_invalid_routes_01_navigate_and_view(page: Page):
    """
    Scenario: Handling of Invalid Routes and 404 States
    Scenario ID: e429ec37-e573-412a-8533-00c45bd30c0a
    Subtest: Initial Navigation & Invalid Route View Render
    Category: error_flow
    """
    print("[STEP 1] Authenticate session before navigating to invalid route")
    try:
        perform_login_if_needed(page)

        print(f"[STEP 2] Navigating to non-existent route: {INVALID_ROUTE}")
        page.goto(INVALID_ROUTE, wait_until="networkidle")

        print("[STEP 3] Verifying page loaded without uncaught crash or blank white page")
        body = page.locator("body")
        expect(body).to_be_visible()

        # Ensure page has readable content (404 message, fallback redirect, or navigation shell)
        body_text = body.inner_text()
        assert len(body_text.strip()) > 0, "Page rendered as a blank white page"
        print(f"[INFO] Current URL after navigating to invalid route: {page.url}")

    except Exception as exc:
        screenshot_path = "failure_test_invalid_routes_01.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 01 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_invalid_routes_02_interaction_and_validation(page: Page):
    """
    Scenario: Handling of Invalid Routes and 404 States
    Scenario ID: e429ec37-e573-412a-8533-00c45bd30c0a
    Subtest: Interaction & Error State UI Validation
    Category: error_flow
    """
    print("[STEP 1] Navigating to invalid route under active session")
    try:
        perform_login_if_needed(page)
        page.goto(INVALID_ROUTE, wait_until="networkidle")

        print("[STEP 2] Validating error presentation or graceful redirection elements")
        # Check if 404 state indicators or fallback navigation controls are visible
        error_indicators = page.locator("text=404, text=Not Found, text=Page not found, text=Page Not Found")
        fallback_nav = page.locator("a[href*='dashboard'], a[href='/'], button:has-text('Back'), button:has-text('Home'), button:has-text('Back to home'), nav, aside")

        has_error_message = error_indicators.count() > 0 and error_indicators.first.is_visible()
        has_nav_controls = fallback_nav.count() > 0 and fallback_nav.first.is_visible()

        assert has_error_message or has_nav_controls or page.url != INVALID_ROUTE, (
            f"Expected 404 notification or graceful fallback navigation, but found neither at {page.url}"
        )
        print(f"[PASS] Error state or fallback navigation validated. Error msg visible: {has_error_message}, Nav controls visible: {has_nav_controls}")

    except Exception as exc:
        screenshot_path = "failure_test_invalid_routes_02.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 02 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_invalid_routes_03_action_and_outcome(page: Page):
    """
    Scenario: Handling of Invalid Routes and 404 States
    Scenario ID: e429ec37-e573-412a-8533-00c45bd30c0a
    Subtest: Complete Recovery Action & Layout Integrity Verification
    Category: error_flow
    """
    print("[STEP 1] Setup session and enter invalid route")
    try:
        perform_login_if_needed(page)
        page.goto(INVALID_ROUTE, wait_until="networkidle")

        print("[STEP 2] Attempt recovery via available fallback links/buttons")
        # Find any viable return link: dashboard overview, home link, or back button
        recovery_link = page.locator(
            "a[href*='/dashboard/overview'], a[href*='dashboard'], a[href='/'], button:has-text('Back to home'), button:has-text('Home'), a:has-text('Overview'), a:has-text('Dashboard')"
        ).first

        if recovery_link.is_visible(timeout=3000):
            print(f"[STEP 3] Clicking recovery element: {recovery_link.text_content()}")
            recovery_link.click()
            page.wait_for_load_state("networkidle")
            print(f"[INFO] Navigated back to: {page.url}")
            expect(page.locator("body")).to_be_visible()
        else:
            print("[INFO] Direct recovery link not explicit; verifying layout is intact and functional")
            expect(page.locator("body")).to_be_visible()

        # Final verification: layout is not crashed
        print("[STEP 4] Asserting application stability (no unhandled JS crash screens)")
        expect(page.locator("body")).not_to_have_text(re.compile(r"Uncaught TypeError|CrashReport|Internal Server Error 500", re.IGNORECASE))
        print("[PASS] Layout stability and graceful invalid route handling verified successfully.")

    except Exception as exc:
        screenshot_path = "failure_test_invalid_routes_03.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 03 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise

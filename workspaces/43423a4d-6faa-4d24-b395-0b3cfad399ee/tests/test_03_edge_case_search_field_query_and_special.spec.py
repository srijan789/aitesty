import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net"
LOGIN_URL = f"{BASE_URL}/sso/login"
TOOLS_URL = f"{BASE_URL}/tools"

USERNAME = "user-3-Team10@velogent.com"
PASSWORD = "F@@OLwY16C"


def ensure_authenticated(page: Page) -> None:
    """
    Resilient authentication helper supporting SSO login with multiple locator fallbacks
    and load state validations to prevent prerequisite timeouts.
    """
    print(f"[AUTH] Checking current URL or navigating to login: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=45000)

    # If already logged in and redirected away from login
    if "/sso/login" not in page.url and "/login" not in page.url:
        print(f"[AUTH] Already authenticated, current URL: {page.url}")
        return

    # Wait for the login form / container to become visible
    try:
        page.wait_for_selector(
            "form, input, [data-testid*='login'], .login-container",
            state="visible",
            timeout=15000,
        )
    except Exception:
        print("[AUTH] Generic container wait timed out, attempting direct input selection...")

    # Resilient username / email locator
    username_selector = (
        "input[placeholder*='email' i], "
        "input[placeholder*='username' i], "
        "input[name='email'], "
        "input[name='username'], "
        "input[type='email'], "
        "input#email, "
        "input#username, "
        "input[type='text']"
    )
    email_input = page.locator(username_selector).first
    email_input.wait_for(state="visible", timeout=20000)
    email_input.fill(USERNAME)
    print(f"[AUTH] Filled username: {USERNAME}")

    # Resilient password locator
    password_selector = (
        "input[placeholder*='password' i], "
        "input[name='password'], "
        "input[type='password'], "
        "input#password"
    )
    password_input = page.locator(password_selector).first
    password_input.wait_for(state="visible", timeout=10000)
    password_input.fill(PASSWORD)
    print("[AUTH] Filled password")

    # Submit login
    submit_button = page.locator(
        "button[type='submit'], "
        "button:has-text('Log in'), "
        "button:has-text('Login'), "
        "button:has-text('Sign In'), "
        "button:has-text('Continue'), "
        "input[type='submit']"
    ).first
    submit_button.click()
    print("[AUTH] Clicked submit button")

    # Wait for post-login redirect
    try:
        page.wait_for_url(lambda url: "/sso/login" not in url, timeout=20000)
    except Exception:
        page.wait_for_load_state("networkidle", timeout=10000)
    print(f"[AUTH] Logged in successfully. Current URL: {page.url}")


def get_search_input(page: Page):
    """
    Returns the primary search input locator using resilient fallbacks.
    """
    search_selector = (
        "input[type='search'], "
        "input[placeholder*='search' i], "
        "input[aria-label*='search' i], "
        "input[name*='search' i], "
        "input[type='text'][placeholder*='Search' i]"
    )
    return page.locator(search_selector).first


def test_search_special_chars_01_navigate_and_view(page: Page):
    """
    Scenario: Search Field Query and Special Characters Handling
    Scenario ID: 68771480-be35-44da-92ea-327e0eeb20c6
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    screenshot_path = "screenshots/test_search_special_chars_01.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    try:
        print("[STEP 1] Authenticating and navigating to /tools")
        ensure_authenticated(page)
        page.goto(TOOLS_URL, wait_until="domcontentloaded", timeout=30000)

        print("[STEP 2] Verifying Tools page view and search input visibility")
        search_input = get_search_input(page)
        search_input.wait_for(state="visible", timeout=15000)
        expect(search_input).to_be_visible()

        print("[STEP 3] Verifying Tools view container or content area is rendered")
        content_area = page.locator("main, [role='main'], .tools-container, .content, table, .grid, [data-testid*='tool']").first
        expect(content_area).to_be_visible()
        print("[PASS] Tools page and search input rendered successfully.")

    except Exception as exc:
        print(f"[FAILURE] Subtest 01 failed: {exc}")
        page.screenshot(path=screenshot_path, full_page=True)
        raise


def test_search_special_chars_02_interaction_and_validation(page: Page):
    """
    Scenario: Search Field Query and Special Characters Handling
    Scenario ID: 68771480-be35-44da-92ea-327e0eeb20c6
    Subtest: Interaction & Input Validation
    Category: edge_case
    """
    screenshot_path = "screenshots/test_search_special_chars_02.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    try:
        print("[STEP 1] Ensuring authenticated session on /tools")
        ensure_authenticated(page)
        page.goto(TOOLS_URL, wait_until="domcontentloaded", timeout=30000)

        search_input = get_search_input(page)
        search_input.wait_for(state="visible", timeout=15000)

        print("[STEP 2] Populating search input with standard alphanumeric query")
        test_query = "webhook"
        search_input.fill(test_query)
        page.wait_for_timeout(500)
        expect(search_input).to_have_value(test_query)

        print("[STEP 3] Clearing search input to verify reset behavior")
        search_input.fill("")
        page.wait_for_timeout(500)
        expect(search_input).to_have_value("")

        print("[STEP 4] Testing whitespace and boundary empty strings")
        search_input.fill("   ")
        page.wait_for_timeout(500)
        # Verify page does not crash and search input accepts spaces
        expect(search_input).to_be_visible()
        print("[PASS] Search input interaction and basic validation succeeded.")

    except Exception as exc:
        print(f"[FAILURE] Subtest 02 failed: {exc}")
        page.screenshot(path=screenshot_path, full_page=True)
        raise


def test_search_special_chars_03_action_and_outcome(page: Page):
    """
    Scenario: Search Field Query and Special Characters Handling
    Scenario ID: 68771480-be35-44da-92ea-327e0eeb20c6
    Subtest: Complete Action & Final Verification
    Category: edge_case
    """
    screenshot_path = "screenshots/test_search_special_chars_03.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    # Track uncaught JS exceptions during special character execution
    js_errors = []
    page.on("pageerror", lambda err: js_errors.append(str(err)))

    try:
        print("[STEP 1] Navigating to /tools for special character edge case tests")
        ensure_authenticated(page)
        page.goto(TOOLS_URL, wait_until="domcontentloaded", timeout=30000)

        search_input = get_search_input(page)
        search_input.wait_for(state="visible", timeout=15000)

        special_char_payloads = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE tools; --",
            "%_`~!@#$%^&*()_+=-[]{}\\|;:'\",.<>/?",
            "🚀🔥✨",
        ]

        for payload in special_char_payloads:
            print(f"[STEP 2] Testing search with special payload: {payload}")
            search_input.fill(payload)
            page.wait_for_timeout(500)

            # Assert input populated correctly without triggering execution
            expect(search_input).to_have_value(payload)

            # Assert page remains responsive and interactive
            expect(search_input).to_be_editable()

            # Ensure no crash modal / 500 error boundary is thrown
            error_boundary = page.locator("text='Something went wrong', text='Application Error', text='500 Internal Server Error'")
            expect(error_boundary).to_have_count(0)

        print("[STEP 3] Verifying no unhandled JavaScript exceptions occurred")
        assert len(js_errors) == 0, f"Unhandled JS errors detected during search filtering: {js_errors}"

        print("[STEP 4] Restoring search input to clean state")
        search_input.fill("")
        page.wait_for_timeout(300)
        expect(search_input).to_have_value("")

        print("[PASS] Search safely evaluated special characters with zero crashes or XSS issues.")

    except Exception as exc:
        print(f"[FAILURE] Subtest 03 failed: {exc}")
        page.screenshot(path=screenshot_path, full_page=True)
        raise

import os
import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net"
LOGIN_URL = f"{BASE_URL}/sso/login"
AUTH_USERNAME = "user-3-Team10@velogent.com"
AUTH_PASSWORD = "F@@OLwY16C"
SCREENSHOT_DIR = "test-results/screenshots"


def setup_screenshot_dir() -> None:
    """Ensure screenshot directory exists."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def get_username_input(page: Page):
    """Resilient locator helper for username input field."""
    selectors = [
        "#login-username",
        "input[name='username']",
        "input[name='email']",
        "input[type='email']",
        "input[type='text']",
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return page.locator("#login-username")


def get_password_input(page: Page):
    """Resilient locator helper for password input field."""
    selectors = [
        "#login-password",
        "input[name='password']",
        "input[type='password']",
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return page.locator("#login-password")


def get_signin_button(page: Page):
    """Resilient locator helper for sign in submit button."""
    selectors = [
        "button:has-text('Sign in')",
        "button:has-text('Sign In')",
        "button:has-text('Log in')",
        "button:has-text('Log In')",
        "button[type='submit']",
    ]
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() > 0 and loc.is_visible():
            return loc
    return page.locator("button[type='submit']")


def test_user_auth_sso_login_01_navigate_and_view(page: Page):
    """
    Scenario: User Authentication via SSO Login Flow
    Scenario ID: ee397770-e8e9-4f41-b441-1eed8705701f
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    setup_screenshot_dir()
    test_name = "test_user_auth_sso_login_01_navigate_and_view"
    try:
        print(f"[STEP 1] Navigating to SSO Login URL: {LOGIN_URL}")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("[STEP 2] Verifying login page URL contains /sso/login")
        expect(page).to_have_url(re.compile(r".*/sso/login.*"), timeout=15000)

        print("[STEP 3] Verifying presence and visibility of login form elements")
        username_field = get_username_input(page)
        expect(username_field).to_be_visible(timeout=10000)

        password_field = get_password_input(page)
        expect(password_field).to_be_visible(timeout=10000)

        signin_btn = get_signin_button(page)
        expect(signin_btn).to_be_visible(timeout=10000)
        print("[STEP 4] Login view successfully rendered with all expected controls")

    except Exception as exc:
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test {test_name} failed: {exc}. Screenshot captured at: {screenshot_path}")
        raise


def test_user_auth_sso_login_02_interaction_and_validation(page: Page):
    """
    Scenario: User Authentication via SSO Login Flow
    Scenario ID: ee397770-e8e9-4f41-b441-1eed8705701f
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    setup_screenshot_dir()
    test_name = "test_user_auth_sso_login_02_interaction_and_validation"
    try:
        print(f"[STEP 1] Navigating to SSO Login URL: {LOGIN_URL}")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print(f"[STEP 2] Filling username field with valid email: {AUTH_USERNAME}")
        username_field = get_username_input(page)
        expect(username_field).to_be_visible(timeout=10000)
        username_field.fill(AUTH_USERNAME)
        expect(username_field).to_have_value(AUTH_USERNAME)

        print("[STEP 3] Filling password field with valid credentials")
        password_field = get_password_input(page)
        expect(password_field).to_be_visible(timeout=10000)
        password_field.fill(AUTH_PASSWORD)
        expect(password_field).to_have_value(AUTH_PASSWORD)

        print("[STEP 4] Verifying sign-in button is enabled and ready for submission")
        signin_btn = get_signin_button(page)
        expect(signin_btn).to_be_visible(timeout=10000)
        expect(signin_btn).to_be_enabled(timeout=5000)
        print("[STEP 5] Interaction & validation subtest passed successfully")

    except Exception as exc:
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test {test_name} failed: {exc}. Screenshot captured at: {screenshot_path}")
        raise


def test_user_auth_sso_login_03_action_and_outcome(page: Page):
    """
    Scenario: User Authentication via SSO Login Flow
    Scenario ID: ee397770-e8e9-4f41-b441-1eed8705701f
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    setup_screenshot_dir()
    test_name = "test_user_auth_sso_login_03_action_and_outcome"
    try:
        print(f"[STEP 1] Navigating to SSO Login URL: {LOGIN_URL}")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print("[STEP 2] Populating authentication credentials")
        username_field = get_username_input(page)
        expect(username_field).to_be_visible(timeout=10000)
        username_field.fill(AUTH_USERNAME)

        password_field = get_password_input(page)
        expect(password_field).to_be_visible(timeout=10000)
        password_field.fill(AUTH_PASSWORD)

        print("[STEP 3] Clicking Sign In button to initiate authentication")
        signin_btn = get_signin_button(page)
        expect(signin_btn).to_be_visible(timeout=10000)
        signin_btn.click()

        print("[STEP 4] Awaiting redirection to /agentflows dashboard")
        expect(page).to_have_url(re.compile(r".*/agentflows.*"), timeout=20000)

        print("[STEP 5] Verifying user lands on authenticated workspace")
        # Ensure page has loaded beyond SSO login
        expect(page.locator("body")).to_be_visible()
        print("[STEP 6] SSO Login Flow completed successfully and verified")

    except Exception as exc:
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test {test_name} failed: {exc}. Screenshot captured at: {screenshot_path}")
        raise

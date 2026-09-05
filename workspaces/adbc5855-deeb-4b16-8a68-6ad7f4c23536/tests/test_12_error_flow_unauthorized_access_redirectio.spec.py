import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
LOGIN_CREDENTIALS = {
    "username": "srijan.psn@gmail.com",
    "password": "Password1"
}


def test_unauthorized_access_01_navigate_and_redirect(page: Page) -> None:
    """
    Scenario: Unauthorized Access Redirection to Login
    Scenario ID: 10497bc9-8553-4604-8276-c35c3b77e761
    Subtest: Initial Navigation & Redirect Verification
    Category: error_flow
    """
    screenshot_path = "screenshots/unauthorized_access_01_failure.png"
    try:
        print("[STEP 1] Ensure clean session context and navigate to protected route '/settings'")
        page.context.clear_cookies()
        page.goto(f"{BASE_URL}/settings", wait_until="networkidle")

        print("[STEP 2] Assert that the application intercepted the request and redirected to /signin with redirect param")
        expect(page).to_have_url(re.compile(r"/signin\?redirect=(%2F|/)settings"), timeout=10000)
        print(f"[STEP 2 PASS] Current URL correctly redirected to: {page.url}")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] test_unauthorized_access_01_navigate_and_redirect failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_unauthorized_access_02_login_form_render(page: Page) -> None:
    """
    Scenario: Unauthorized Access Redirection to Login
    Scenario ID: 10497bc9-8553-4604-8276-c35c3b77e761
    Subtest: Interaction & Input Validation on Redirected Login Form
    Category: error_flow
    """
    screenshot_path = "screenshots/unauthorized_access_02_failure.png"
    try:
        print("[STEP 1] Navigate directly to protected route without session")
        page.context.clear_cookies()
        page.goto(f"{BASE_URL}/settings", wait_until="networkidle")

        print("[STEP 2] Assert login form elements are present and visible")
        # Target #emailOrLdapLoginId with fallback to standard input selectors
        email_input = page.locator("#emailOrLdapLoginId, input[name='emailOrLdapLoginId'], input[name='email'], input[type='email']").first
        expect(email_input).to_be_visible(timeout=10000)

        password_input = page.locator("input[name='password'], input[type='password']").first
        expect(password_input).to_be_visible(timeout=10000)

        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first
        expect(submit_btn).to_be_visible(timeout=10000)

        print("[STEP 3] Assert protected content is not leaked on page")
        settings_heading = page.locator("h1:has-text('Settings'), h2:has-text('Settings')")
        expect(settings_heading).not_to_be_visible()
        print("[STEP 3 PASS] Login form is displayed and protected content is secured.")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] test_unauthorized_access_02_login_form_render failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_unauthorized_access_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Unauthorized Access Redirection to Login
    Scenario ID: 10497bc9-8553-4604-8276-c35c3b77e761
    Subtest: Complete Action & Post-Auth Destination Verification
    Category: error_flow
    """
    screenshot_path = "screenshots/unauthorized_access_03_failure.png"
    try:
        print("[STEP 1] Navigate to protected route '/settings' while unauthenticated")
        page.context.clear_cookies()
        page.goto(f"{BASE_URL}/settings", wait_until="networkidle")

        print("[STEP 2] Fill valid credentials into the redirected login form")
        email_input = page.locator("#emailOrLdapLoginId, input[name='emailOrLdapLoginId'], input[name='email'], input[type='email']").first
        expect(email_input).to_be_visible(timeout=10000)
        email_input.fill(LOGIN_CREDENTIALS["username"])

        password_input = page.locator("input[name='password'], input[type='password']").first
        expect(password_input).to_be_visible(timeout=10000)
        password_input.fill(LOGIN_CREDENTIALS["password"])

        print("[STEP 3] Submit login form and verify redirection back to target /settings route")
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first
        submit_btn.click()

        expect(page).to_have_url(re.compile(r"/settings"), timeout=15000)
        print(f"[STEP 3 PASS] Successfully logged in and redirected back to: {page.url}")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] test_unauthorized_access_03_action_and_outcome failed: {exc}. Screenshot saved to {screenshot_path}")
        raise

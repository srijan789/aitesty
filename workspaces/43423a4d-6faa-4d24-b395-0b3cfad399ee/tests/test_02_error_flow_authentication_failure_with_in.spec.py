import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net/sso/login"


def test_auth_failure_invalid_creds_01_navigate_and_view(page: Page):
    """
    Scenario: Authentication Failure with Invalid Credentials
    Scenario ID: 3d2a7fc8-8776-4d22-95d4-5965cebf8107
    Subtest: Initial Navigation & View Render
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to /sso/login")
        page.goto(BASE_URL, wait_until="domcontentloaded")

        print("[STEP 2] Verify login view elements are rendered")
        username_input = page.locator("#login-username").or_(page.locator('input[name="username"], input[type="text"], input[type="email"]')).first
        password_input = page.locator("#login-password").or_(page.locator('input[name="password"], input[type="password"]')).first
        submit_btn = page.locator('button:has-text("Sign in")').or_(page.get_by_role("button", name=re.compile(r"sign in|log in|submit", re.IGNORECASE))).first

        expect(username_input).to_be_visible(timeout=10000)
        expect(password_input).to_be_visible(timeout=10000)
        expect(submit_btn).to_be_visible(timeout=10000)

        print("[STEP 3] Confirm URL matches SSO login path")
        expect(page).to_have_url(re.compile(r"/sso/login"))
    except Exception as e:
        screenshot_path = "failure_auth_failure_01_nav.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] View render failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_auth_failure_invalid_creds_02_interaction_and_validation(page: Page):
    """
    Scenario: Authentication Failure with Invalid Credentials
    Scenario ID: 3d2a7fc8-8776-4d22-95d4-5965cebf8107
    Subtest: Interaction & Input Validation
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to /sso/login")
        page.goto(BASE_URL, wait_until="domcontentloaded")

        username_input = page.locator("#login-username").or_(page.locator('input[name="username"], input[type="text"], input[type="email"]')).first
        password_input = page.locator("#login-password").or_(page.locator('input[name="password"], input[type="password"]')).first

        print("[STEP 2] Fill invalid/non-existent user credentials into inputs")
        invalid_user = "nonexistent_user_99999@velogent.com"
        invalid_pass = "InvalidPassword!999"

        username_input.fill(invalid_user)
        expect(username_input).to_have_value(invalid_user)

        password_input.fill(invalid_pass)
        expect(password_input).to_have_value(invalid_pass)

        print("[STEP 3] Verify input fields accepted data successfully")
    except Exception as e:
        screenshot_path = "failure_auth_failure_02_input.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Input validation failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_auth_failure_invalid_creds_03_action_and_outcome(page: Page):
    """
    Scenario: Authentication Failure with Invalid Credentials
    Scenario ID: 3d2a7fc8-8776-4d22-95d4-5965cebf8107
    Subtest: Complete Action & Final Verification
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to /sso/login")
        page.goto(BASE_URL, wait_until="domcontentloaded")

        username_input = page.locator("#login-username").or_(page.locator('input[name="username"], input[type="text"], input[type="email"]')).first
        password_input = page.locator("#login-password").or_(page.locator('input[name="password"], input[type="password"]')).first
        submit_btn = page.locator('button:has-text("Sign in")').or_(page.get_by_role("button", name=re.compile(r"sign in|log in|submit", re.IGNORECASE))).first

        print("[STEP 2] Fill non-existent user credentials")
        username_input.fill("nonexistent_user_99999@velogent.com")
        password_input.fill("WrongPassword123!")

        print("[STEP 3] Click Sign in button and trigger authentication request")
        submit_btn.click()

        print("[STEP 4] Verify error message / alert banner is displayed")
        error_locator = page.locator('[role="alert"], .error, .error-message, .alert, .ant-alert, [data-testid="error-message"]').or_(
            page.get_by_text(re.compile(r"invalid|incorrect|unauthorized|failed|error|not found|wrong", re.IGNORECASE))
        ).first

        expect(error_locator).to_be_visible(timeout=10000)

        print("[STEP 5] Verify user is retained on the login page with no active session")
        expect(page).to_have_url(re.compile(r"/sso/login"))
    except Exception as e:
        screenshot_path = "failure_auth_failure_03_action.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Action & outcome verification failed: {e}. Screenshot captured at {screenshot_path}")
        raise

import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
SIGNIN_URL = f"{BASE_URL}/signin"
VALID_EMAIL = "srijan.psn@gmail.com"
INVALID_PASSWORD = "WrongPassword999!"

SCREENSHOT_DIR = "test-results/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def test_invalid_password_01_navigate_and_view(page: Page):
    """
    Scenario: Sign-In Rejection with Invalid Password
    Scenario ID: a82fe2d8-4575-4cc0-b67b-cca4c8754b99
    Subtest: Initial Navigation & View Render
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(SIGNIN_URL, wait_until="domcontentloaded")

        print("[STEP 2] Verify signin form elements are visible")
        email_input = page.locator('input[name="email"], input[type="email"], #emailOrLdapLoginId').first
        password_input = page.locator('input[name="password"], input[type="password"], #password').first
        submit_button = page.locator('button:has-text("Sign in"), button[type="submit"]').first

        expect(email_input).to_be_visible(timeout=10000)
        expect(password_input).to_be_visible(timeout=10000)
        expect(submit_button).to_be_visible(timeout=10000)
        expect(page).to_have_url(lambda url: "/signin" in url)

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "invalid_pwd_01_failure.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {e}. Screenshot captured at: {screenshot_path}")
        raise


def test_invalid_password_02_interaction_and_validation(page: Page):
    """
    Scenario: Sign-In Rejection with Invalid Password
    Scenario ID: a82fe2d8-4575-4cc0-b67b-cca4c8754b99
    Subtest: Interaction & Input Validation
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(SIGNIN_URL, wait_until="domcontentloaded")

        print(f"[STEP 2] Fill valid email: {VALID_EMAIL}")
        email_input = page.locator('input[name="email"], input[type="email"], #emailOrLdapLoginId').first
        email_input.fill(VALID_EMAIL)
        expect(email_input).to_have_value(VALID_EMAIL)

        print("[STEP 3] Fill invalid password")
        password_input = page.locator('input[name="password"], input[type="password"], #password').first
        password_input.fill(INVALID_PASSWORD)
        expect(password_input).to_have_value(INVALID_PASSWORD)

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "invalid_pwd_02_failure.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {e}. Screenshot captured at: {screenshot_path}")
        raise


def test_invalid_password_03_action_and_outcome(page: Page):
    """
    Scenario: Sign-In Rejection with Invalid Password
    Scenario ID: a82fe2d8-4575-4cc0-b67b-cca4c8754b99
    Subtest: Complete Action & Final Verification
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(SIGNIN_URL, wait_until="domcontentloaded")

        print(f"[STEP 2] Fill email with '{VALID_EMAIL}'")
        email_input = page.locator('input[name="email"], input[type="email"], #emailOrLdapLoginId').first
        email_input.fill(VALID_EMAIL)

        print(f"[STEP 3] Fill password with invalid credentials")
        password_input = page.locator('input[name="password"], input[type="password"], #password').first
        password_input.fill(INVALID_PASSWORD)

        print("[STEP 4] Click Sign In button")
        submit_button = page.locator('button:has-text("Sign in"), button[type="submit"]').first
        submit_button.click()

        print("[STEP 5] Verify error feedback and ensure user remains on /signin")
        # Check that error notification / message appears (toast, alert, or inline notification)
        error_notification = page.locator(
            '.el-notification--error, .el-message--error, [role="alert"], .notification-error, '
            ':text("Invalid"), :text("incorrect"), :text("password"), :text("Unauthorized"), :text("authentication failed")'
        ).first

        expect(error_notification).to_be_visible(timeout=10000)

        # Confirm user remains on the signin page and no authenticated dashboard is accessed
        expect(page).to_have_url(lambda url: "/signin" in url)

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "invalid_pwd_03_failure.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {e}. Screenshot captured at: {screenshot_path}")
        raise

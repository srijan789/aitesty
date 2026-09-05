import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
SCREENSHOT_DIR = "screenshots"


@pytest.fixture(autouse=True)
def ensure_screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def test_invalid_credentials_01_navigate_and_view(page: Page):
    """
    Scenario: Admin Authentication Rejection with Invalid Credentials
    Scenario ID: 429af089-6233-4c9e-b356-fcaeb6457057
    Subtest: Initial Navigation & View Render
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to login page")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        print("[STEP 2] Verify login form controls are rendered")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]')
        password_input = page.locator('input[type="password"], input[name="password"]')
        submit_button = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")')

        expect(email_input.first).to_be_visible(timeout=10000)
        expect(password_input.first).to_be_visible(timeout=10000)
        expect(submit_button.first).to_be_visible(timeout=10000)
        print("[INFO] Login page rendered successfully with email, password, and submit controls.")

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "error_429af089_01_navigate_failed.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Initial view render failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_invalid_credentials_02_interaction_and_validation(page: Page):
    """
    Scenario: Admin Authentication Rejection with Invalid Credentials
    Scenario ID: 429af089-6233-4c9e-b356-fcaeb6457057
    Subtest: Interaction & Input Validation
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to login page")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        password_input = page.locator('input[type="password"], input[name="password"]').first

        print("[STEP 2] Fill email field with valid admin username")
        email_input.fill("admin@nanotrak.com")
        expect(email_input).to_have_value("admin@nanotrak.com")

        print("[STEP 3] Fill password field with invalid password string")
        password_input.fill("WrongPassword123")
        expect(password_input).to_have_value("WrongPassword123")

        print("[INFO] Input fields correctly filled and validated.")

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "error_429af089_02_interaction_failed.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Input interaction failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_invalid_credentials_03_action_and_outcome(page: Page):
    """
    Scenario: Admin Authentication Rejection with Invalid Credentials
    Scenario ID: 429af089-6233-4c9e-b356-fcaeb6457057
    Subtest: Complete Action & Final Verification
    Category: error_flow
    """
    try:
        print("[STEP 1] Navigate to login page")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        password_input = page.locator('input[type="password"], input[name="password"]').first
        submit_button = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first

        print("[STEP 2] Fill invalid credentials")
        email_input.fill("admin@nanotrak.com")
        password_input.fill("WrongPassword123")

        print("[STEP 3] Click Sign in button to submit invalid authentication request")
        submit_button.click()

        print("[STEP 4] Verify authentication is rejected with error feedback")
        # Check for alert, notification, toast, or invalid credentials feedback
        error_feedback = page.locator(
            '[role="alert"], .ant-message, .ant-notification, .toast, .alert, '
            ':text-matches("invalid|incorrect|failed|unauthorized|error|wrong", "i")'
        )
        expect(error_feedback.first).to_be_visible(timeout=10000)

        print("[STEP 5] Verify user is not redirected to dashboard and remains on login view")
        expect(page).not_to_have_url(".*/dashboard.*", timeout=5000)
        expect(page.locator('input[type="password"], input[name="password"]').first).to_be_visible(timeout=5000)
        print("[INFO] Authentication successfully rejected; error feedback displayed and user remained on login page.")

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "error_429af089_03_action_outcome_failed.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Rejection verification failed: {e}. Screenshot captured at {screenshot_path}")
        raise

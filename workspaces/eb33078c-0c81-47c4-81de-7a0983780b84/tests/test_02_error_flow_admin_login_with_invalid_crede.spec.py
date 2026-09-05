import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
SCREENSHOT_DIR = "screenshots"


def ensure_screenshot_dir():
    """Ensure the screenshot directory exists."""
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def capture_failure_screenshot(page: Page, test_name: str):
    """Capture a screenshot on failure with proper error logging."""
    ensure_screenshot_dir()
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[DIAGNOSTIC] Failure screenshot saved to: {screenshot_path}")
    except Exception as e:
        print(f"[DIAGNOSTIC] Failed to capture screenshot: {e}")


def test_invalid_login_01_navigate_and_view(page: Page):
    """
    Scenario: Admin Login with Invalid Credentials Error Flow
    Scenario ID: 12b19a64-996d-475c-ae09-a248433f0449
    Subtest: Initial Navigation & View Render
    Category: error_flow
    """
    test_name = "test_invalid_login_01_navigate_and_view"
    try:
        print("[STEP 1] Navigate to login page")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        print("[STEP 2] Verify login view elements are rendered")
        # Verify email input is visible
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="username" i]').first
        expect(email_input).to_be_visible(timeout=10000)

        # Verify password input is visible
        password_input = page.locator('input[type="password"], input[name="password"]').first
        expect(password_input).to_be_visible(timeout=10000)

        # Verify submit/sign in button is visible
        sign_in_btn = page.locator('button:has-text("Sign in"), button:has-text("Log in"), button[type="submit"]').first
        expect(sign_in_btn).to_be_visible(timeout=10000)

        print("[STEP 3] Verified login form elements rendered successfully")
    except Exception as exc:
        capture_failure_screenshot(page, test_name)
        raise exc


def test_invalid_login_02_interaction_and_validation(page: Page):
    """
    Scenario: Admin Login with Invalid Credentials Error Flow
    Scenario ID: 12b19a64-996d-475c-ae09-a248433f0449
    Subtest: Interaction & Input Validation
    Category: error_flow
    """
    test_name = "test_invalid_login_02_interaction_and_validation"
    try:
        print("[STEP 1] Navigate to login page")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        invalid_email = "invalid_admin@nanotrak.com"
        invalid_password = "WrongPassword!999"

        print("[STEP 2] Fill invalid email into email input field")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="username" i]').first
        expect(email_input).to_be_visible(timeout=10000)
        email_input.fill(invalid_email)

        print("[STEP 3] Fill invalid password into password input field")
        password_input = page.locator('input[type="password"], input[name="password"]').first
        expect(password_input).to_be_visible(timeout=10000)
        password_input.fill(invalid_password)

        print("[STEP 4] Verify field input values are set correctly")
        expect(email_input).to_have_value(invalid_email)
        expect(password_input).to_have_value(invalid_password)

    except Exception as exc:
        capture_failure_screenshot(page, test_name)
        raise exc


def test_invalid_login_03_action_and_outcome(page: Page):
    """
    Scenario: Admin Login with Invalid Credentials Error Flow
    Scenario ID: 12b19a64-996d-475c-ae09-a248433f0449
    Subtest: Complete Action & Final Verification
    Category: error_flow
    """
    test_name = "test_invalid_login_03_action_and_outcome"
    try:
        print("[STEP 1] Navigate to login page")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

        invalid_email = "unauthorized_user@nanotrak.com"
        invalid_password = "InvalidSecretPassword123"

        print("[STEP 2] Fill invalid credentials")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[placeholder*="username" i]').first
        password_input = page.locator('input[type="password"], input[name="password"]').first

        email_input.fill(invalid_email)
        password_input.fill(invalid_password)

        print("[STEP 3] Click Sign in button to submit invalid credentials")
        sign_in_btn = page.locator('button:has-text("Sign in"), button:has-text("Log in"), button[type="submit"]').first
        expect(sign_in_btn).to_be_enabled(timeout=5000)
        sign_in_btn.click()

        print("[STEP 4] Assert error alert/notification is displayed or rejection feedback appears")
        # Target alerts, toast messages, error text containers, or inline validation
        error_locator = page.locator(
            'div[role="alert"], '
            '.toast, '
            '.notification, '
            '.alert, '
            '.error-message, '
            ':has-text("Invalid credentials"), '
            ':has-text("invalid"), '
            ':has-text("Incorrect"), '
            ':has-text("failed"), '
            ':has-text("Unauthorized"), '
            ':has-text("User not found")'
        ).first

        # Wait for error feedback to become visible
        expect(error_locator).to_be_visible(timeout=10000)
        print(f"[STEP 4.1] Error message captured: {error_locator.inner_text()}")

        print("[STEP 5] Assert user is not authenticated and remains on login view")
        # Verify user has NOT navigated to an internal dashboard route
        expect(page).not_to_have_url(r".*/(dashboard|home|devices|analytics).*", timeout=5000)

        # Re-verify the sign-in form is still present
        expect(sign_in_btn).to_be_visible(timeout=5000)
        print("[STEP 6] Confirmed authentication rejection and user remains on login page.")

    except Exception as exc:
        capture_failure_screenshot(page, test_name)
        raise exc

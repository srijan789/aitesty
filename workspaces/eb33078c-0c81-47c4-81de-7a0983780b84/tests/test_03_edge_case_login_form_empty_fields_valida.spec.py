import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"


def take_failure_screenshot(page: Page, test_name: str) -> None:
    """Helper function to capture failure screenshots."""
    os.makedirs("screenshots", exist_ok=True)
    screenshot_path = os.path.join("screenshots", f"failed_{test_name}.png")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[DIAGNOSTIC] Screenshot saved on failure: {screenshot_path}")
    except Exception as exc:
        print(f"[DIAGNOSTIC] Failed to capture screenshot: {exc}")


def test_login_empty_fields_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Login Form Empty Fields Validation
    Scenario ID: 1d102489-fe3c-4925-bcdb-b8aedbb7776f
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    test_name = "test_login_empty_fields_01_navigate_and_view"
    try:
        print("[STEP 1] Navigating to login page at BASE_URL")
        page.goto(BASE_URL, wait_until="networkidle")

        print("[STEP 2] Verifying login page components are rendered and inputs are empty")
        # Identify email/username and password fields
        email_input = page.locator('input[type="email"], input[name="username"], input[name="email"], input#username, input#email').first
        password_input = page.locator('input[type="password"], input[name="password"], input#password').first
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Sign in"), button:has-text("Login")').first

        expect(email_input).to_be_visible(timeout=10000)
        expect(password_input).to_be_visible(timeout=10000)
        expect(submit_btn).to_be_visible(timeout=10000)

        # Assert input fields are initially empty
        expect(email_input).to_have_value("")
        expect(password_input).to_have_value("")
        print("[ASSERTION PASSED] Login view rendered properly with empty input fields.")

    except Exception as exc:
        take_failure_screenshot(page, test_name)
        print(f"[ERROR] Test failed in {test_name}: {exc}")
        raise exc


def test_login_empty_fields_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Login Form Empty Fields Validation
    Scenario ID: 1d102489-fe3c-4925-bcdb-b8aedbb7776f
    Subtest: Interaction & Input Validation
    Category: edge_case
    """
    test_name = "test_login_empty_fields_02_interaction_and_validation"
    try:
        print("[STEP 1] Navigating to login page")
        page.goto(BASE_URL, wait_until="networkidle")

        email_input = page.locator('input[type="email"], input[name="username"], input[name="email"], input#username, input#email').first
        password_input = page.locator('input[type="password"], input[name="password"], input#password').first
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Sign in"), button:has-text("Login")').first

        print("[STEP 2] Clicking submit button with all fields empty")
        submit_btn.click()

        print("[STEP 3] Verifying submission was blocked and form validation was triggered")
        # Check that we remain on the login page URL (did not navigate away)
        expect(page).to_have_url(f"{BASE_URL}/", timeout=5000)

        # Verify client-side / HTML5 invalid state or required prompt
        # Check if email/username input is flagged as invalid or has required validation message
        is_email_invalid = email_input.evaluate("(el) => !el.checkValidity() || el.validity.valueMissing")
        is_password_invalid = password_input.evaluate("(el) => !el.checkValidity() || el.validity.valueMissing")

        # Or check for visible error messages on the page
        error_msg = page.locator('.error, .invalid-feedback, [role="alert"], :has-text("required"), :has-text("Please fill")')
        has_error_msg = error_msg.count() > 0

        assert is_email_invalid or is_password_invalid or has_error_msg, (
            "Form submission was expected to trigger validation errors on empty fields, but none were detected."
        )

        print("[ASSERTION PASSED] Submission blocked and validation successfully triggered on empty form.")

    except Exception as exc:
        take_failure_screenshot(page, test_name)
        print(f"[ERROR] Test failed in {test_name}: {exc}")
        raise exc


def test_login_empty_fields_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Login Form Empty Fields Validation
    Scenario ID: 1d102489-fe3c-4925-bcdb-b8aedbb7776f
    Subtest: Complete Action & Final Verification
    Category: edge_case
    """
    test_name = "test_login_empty_fields_03_action_and_outcome"
    try:
        print("[STEP 1] Navigating to login page")
        page.goto(BASE_URL, wait_until="networkidle")

        email_input = page.locator('input[type="email"], input[name="username"], input[name="email"], input#username, input#email').first
        password_input = page.locator('input[type="password"], input[name="password"], input#password').first
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign In"), button:has-text("Sign in"), button:has-text("Login")').first

        print("[STEP 2] Testing partial fill: Fill only email and attempt submit")
        email_input.fill("admin@nanotrak.com")
        password_input.fill("")
        submit_btn.click()

        # Verify password validation prevents submission
        is_password_invalid = password_input.evaluate("(el) => !el.checkValidity() || el.validity.valueMissing")
        expect(page).to_have_url(f"{BASE_URL}/", timeout=5000)
        assert is_password_invalid, "Password field should fail validation when empty."
        print("[STEP 2 VERIFIED] Empty password blocked submission.")

        print("[STEP 3] Testing partial fill: Fill only password and attempt submit")
        email_input.fill("")
        password_input.fill("Nanotrak@123")
        submit_btn.click()

        # Verify email validation prevents submission
        is_email_invalid = email_input.evaluate("(el) => !el.checkValidity() || el.validity.valueMissing")
        expect(page).to_have_url(f"{BASE_URL}/", timeout=5000)
        assert is_email_invalid, "Email field should fail validation when empty."
        print("[STEP 3 VERIFIED] Empty email blocked submission.")

        print("[ASSERTION PASSED] All partial and empty field combinations properly blocked form submission.")

    except Exception as exc:
        take_failure_screenshot(page, test_name)
        print(f"[ERROR] Test failed in {test_name}: {exc}")
        raise exc

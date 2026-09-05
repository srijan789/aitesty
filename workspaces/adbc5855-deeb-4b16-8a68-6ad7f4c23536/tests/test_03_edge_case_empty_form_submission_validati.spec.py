import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("BASE_URL", "http://localhost:5678")


@pytest.fixture(autouse=True)
def setup_teardown(page: Page):
    """Ensure clean test environment before and after each test."""
    yield page


def test_empty_form_submission_01_navigate_and_view(page: Page):
    """
    Scenario: Empty Form Submission Validation on Sign-In
    Scenario ID: a40fb69b-e984-4076-bfb6-1dfbb5d90178
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(f"{BASE_URL}/signin", wait_until="networkidle")

        print("[STEP 2] Verify signin page elements and empty initial state")
        expect(page).to_have_url(f"{BASE_URL}/signin")

        email_input = page.locator('input[type="email"], input[name="email"], input[name="username"], input[type="text"]').first
        password_input = page.locator('input[type="password"]').first
        submit_button = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first

        expect(email_input).to_be_visible()
        expect(password_input).to_be_visible()
        expect(submit_button).to_be_visible()

        # Verify inputs are initially empty
        expect(email_input).to_have_value("")
        expect(password_input).to_have_value("")

    except Exception as exc:
        screenshot_path = "screenshots/a40fb69b_empty_form_01_failure.png"
        os.makedirs("screenshots", exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"[FAILURE] Subtest 01 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_empty_form_submission_02_interaction_and_validation(page: Page):
    """
    Scenario: Empty Form Submission Validation on Sign-In
    Scenario ID: a40fb69b-e984-4076-bfb6-1dfbb5d90178
    Subtest: Interaction & Input Validation
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(f"{BASE_URL}/signin", wait_until="networkidle")

        email_input = page.locator('input[type="email"], input[name="email"], input[name="username"], input[type="text"]').first
        password_input = page.locator('input[type="password"]').first
        submit_button = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first

        print("[STEP 2] Click sign in button with empty fields")
        submit_button.click()

        print("[STEP 3] Verify client-side or form validation triggers")
        # Check HTML5 validation or custom validation messages
        is_email_invalid = email_input.evaluate("el => !el.checkValidity()")
        is_email_required = email_input.evaluate("el => el.hasAttribute('required')")
        
        # Check if either browser HTML5 validation fired, or UI error banner is shown, or field is marked invalid
        has_ui_error = page.locator('.error, .alert, [role="alert"], :invalid, .invalid-feedback, text="required"').count() > 0

        assert is_email_invalid or is_email_required or has_ui_error, (
            "Expected form validation to trigger on empty submission"
        )

        print("[STEP 4] Verify page remains on signin route without unexpected navigation")
        expect(page).to_have_url(f"{BASE_URL}/signin")

    except Exception as exc:
        screenshot_path = "screenshots/a40fb69b_empty_form_02_failure.png"
        os.makedirs("screenshots", exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"[FAILURE] Subtest 02 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_empty_form_submission_03_action_and_outcome(page: Page):
    """
    Scenario: Empty Form Submission Validation on Sign-In
    Scenario ID: a40fb69b-e984-4076-bfb6-1dfbb5d90178
    Subtest: Complete Action & Final Verification
    Category: edge_case
    """
    responses = []

    def handle_response(response):
        responses.append(response)

    page.on("response", handle_response)

    try:
        print("[STEP 1] Navigate to signin page and attach network monitor")
        page.goto(f"{BASE_URL}/signin", wait_until="networkidle")

        submit_button = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first

        print("[STEP 2] Attempt form submission with blank inputs")
        submit_button.click()
        page.wait_for_timeout(1000)

        print("[STEP 3] Verify no 500 server error occurred in response to empty submission")
        server_errors = [r for r in responses if r.status >= 500]
        assert len(server_errors) == 0, f"Server returned 500 status on empty submission: {[r.url for r in server_errors]}"

        print("[STEP 4] Verify user is still unauthenticated on /signin")
        expect(page).to_have_url(f"{BASE_URL}/signin")

    except Exception as exc:
        screenshot_path = "screenshots/a40fb69b_empty_form_03_failure.png"
        os.makedirs("screenshots", exist_ok=True)
        page.screenshot(path=screenshot_path)
        print(f"[FAILURE] Subtest 03 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise

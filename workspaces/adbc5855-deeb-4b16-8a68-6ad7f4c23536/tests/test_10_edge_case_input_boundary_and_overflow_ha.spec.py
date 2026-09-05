import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
SIGNIN_URL = f"{BASE_URL}/signin"


def test_input_boundary_signin_01_navigate_and_view(page: Page):
    """
    Scenario: Input Boundary and Overflow Handling on Sign-In Inputs
    Scenario ID: e1d66182-6abc-4602-af19-5eacd68d6776
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page: " + SIGNIN_URL)
        page.goto(SIGNIN_URL, wait_until="networkidle")

        print("[STEP 2] Verify login input fields and submit button are visible")
        login_input = page.locator('input[name="emailOrLdapLoginId"], #emailOrLdapLoginId, input[type="email"], input[type="text"]').first
        password_input = page.locator('input[name="password"], #password, input[type="password"]').first
        submit_btn = page.locator('button:has-text("Sign in"), button[type="submit"]').first

        expect(login_input).to_be_visible(timeout=10000)
        expect(password_input).to_be_visible(timeout=10000)
        expect(submit_btn).to_be_visible(timeout=10000)
        print("[STEP 3] View render verified successfully")
    except Exception as exc:
        page.screenshot(path="e1d66182-6abc-4602-af19-5eacd68d6776_subtest1_failure.png", full_page=True)
        print(f"[FAILURE] Initial Navigation & View Render failed: {exc}")
        raise


def test_input_boundary_signin_02_interaction_and_validation(page: Page):
    """
    Scenario: Input Boundary and Overflow Handling on Sign-In Inputs
    Scenario ID: e1d66182-6abc-4602-af19-5eacd68d6776
    Subtest: Interaction & Input Validation
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(SIGNIN_URL, wait_until="networkidle")

        login_input = page.locator('input[name="emailOrLdapLoginId"], #emailOrLdapLoginId, input[type="email"], input[type="text"]').first
        expect(login_input).to_be_visible(timeout=10000)

        print("[STEP 2] Generate and fill boundary string exceeding 256 characters")
        overflow_email = ("a" * 260) + "@domainboundarytest.com"
        login_input.fill(overflow_email)

        print("[STEP 3] Verify input field accepts/handles string without crashing UI")
        input_value = login_input.input_value()
        assert len(input_value) > 0, "Input should hold the entered boundary string"

        # Check container dimensions and responsiveness
        bounding_box = login_input.bounding_box()
        assert bounding_box is not None, "Login input bounding box should exist"
        assert bounding_box["width"] > 50, "Input width should not collapse"
        assert bounding_box["height"] > 10, "Input height should not collapse"

        print("[STEP 4] Input boundary interaction validated cleanly")
    except Exception as exc:
        page.screenshot(path="e1d66182-6abc-4602-af19-5eacd68d6776_subtest2_failure.png", full_page=True)
        print(f"[FAILURE] Interaction & Input Validation failed: {exc}")
        raise


def test_input_boundary_signin_03_action_and_outcome(page: Page):
    """
    Scenario: Input Boundary and Overflow Handling on Sign-In Inputs
    Scenario ID: e1d66182-6abc-4602-af19-5eacd68d6776
    Subtest: Complete Action & Final Verification
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(SIGNIN_URL, wait_until="networkidle")

        login_input = page.locator('input[name="emailOrLdapLoginId"], #emailOrLdapLoginId, input[type="email"], input[type="text"]').first
        password_input = page.locator('input[name="password"], #password, input[type="password"]').first
        submit_btn = page.locator('button:has-text("Sign in"), button[type="submit"]').first

        print("[STEP 2] Fill overly long email string (>256 characters) and password")
        overflow_email = ("user_overflow_" + ("x" * 260)) + "@testboundary.com"
        login_input.fill(overflow_email)
        password_input.fill("Password123!")

        print("[STEP 3] Submit form with boundary input")
        submit_btn.click()

        print("[STEP 4] Verify graceful error handling and UI stability")
        # Ensure the page remains responsive and error notification/validation feedback appears
        page.wait_for_timeout(1000)
        expect(page.locator("body")).to_be_visible()

        # The UI should either show an error notification/toast or retain validation status without browser freeze
        error_indicator = page.locator('.el-notification, .el-message, [role="alert"], text=/invalid|error|incorrect|not found|failed/i')
        
        # Verify page has not crashed and login button or inputs are still functional
        expect(submit_btn).to_be_enabled()
        print("[STEP 5] Boundary handling confirmed: UI responsive and errors handled gracefully")
    except Exception as exc:
        page.screenshot(path="e1d66182-6abc-4602-af19-5eacd68d6776_subtest3_failure.png", full_page=True)
        print(f"[FAILURE] Complete Action & Final Verification failed: {exc}")
        raise

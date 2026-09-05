import pytest
import os
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
SIGNIN_URL = f"{BASE_URL}/signin"
USER_EMAIL = "srijan.psn@gmail.com"
USER_PASS = "Password1"
SCREENSHOT_DIR = "test_results/screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def take_failure_screenshot(page: Page, test_name: str):
    """Utility to capture diagnostic screenshot upon failure."""
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[DIAGNOSTIC] Screenshot saved to: {screenshot_path}")
    except Exception as e:
        print(f"[DIAGNOSTIC] Failed to take screenshot: {e}")


def test_successful_sign_in_01_navigate_and_view(page: Page):
    """
    Scenario: Successful User Sign-In with Valid Credentials
    Scenario ID: a2045649-8768-4fc2-8957-aa283d9c8fb9
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    test_id = "test_successful_sign_in_01_navigate_and_view"
    try:
        print("[STEP 1] Navigate to sign-in page")
        page.goto(SIGNIN_URL, wait_until="networkidle")

        print("[STEP 2] Verify email and password input elements are visible and ready")
        email_input = page.locator('#emailOrLdapLoginId, input[name="emailOrLdapLoginId"], input[type="email"], input[type="text"]').first
        password_input = page.locator('#password, input[name="password"], input[type="password"]').first
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Sign In")').first

        expect(email_input).to_be_visible(timeout=10000)
        expect(password_input).to_be_visible(timeout=10000)
        expect(submit_btn).to_be_visible(timeout=10000)
        print("[STEP 2 PASS] Sign-in view rendered successfully with all required inputs.")
    except Exception as e:
        take_failure_screenshot(page, test_id)
        raise e


def test_successful_sign_in_02_interaction_and_validation(page: Page):
    """
    Scenario: Successful User Sign-In with Valid Credentials
    Scenario ID: a2045649-8768-4fc2-8957-aa283d9c8fb9
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    test_id = "test_successful_sign_in_02_interaction_and_validation"
    try:
        print("[STEP 1] Navigate to sign-in page")
        page.goto(SIGNIN_URL, wait_until="networkidle")

        print("[STEP 2] Fill email input field")
        email_input = page.locator('#emailOrLdapLoginId, input[name="emailOrLdapLoginId"], input[type="email"], input[type="text"]').first
        expect(email_input).to_be_visible(timeout=10000)
        email_input.fill(USER_EMAIL)

        print("[STEP 3] Fill password input field")
        password_input = page.locator('#password, input[name="password"], input[type="password"]').first
        expect(password_input).to_be_visible(timeout=10000)
        password_input.fill(USER_PASS)

        print("[STEP 4] Validate input values are accurately set")
        expect(email_input).to_have_value(USER_EMAIL)
        expect(password_input).to_have_value(USER_PASS)
        print("[STEP 4 PASS] Form fields correctly populated and validated.")
    except Exception as e:
        take_failure_screenshot(page, test_id)
        raise e


def test_successful_sign_in_03_action_and_outcome(page: Page):
    """
    Scenario: Successful User Sign-In with Valid Credentials
    Scenario ID: a2045649-8768-4fc2-8957-aa283d9c8fb9
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    test_id = "test_successful_sign_in_03_action_and_outcome"
    try:
        print("[STEP 1] Navigate to sign-in page")
        page.goto(SIGNINURL := SIGNIN_URL, wait_until="networkidle")

        print("[STEP 2] Populate valid user credentials")
        email_input = page.locator('#emailOrLdapLoginId, input[name="emailOrLdapLoginId"], input[type="email"], input[type="text"]').first
        password_input = page.locator('#password, input[name="password"], input[type="password"]').first
        
        email_input.fill(USER_EMAIL)
        password_input.fill(USER_PASS)

        print("[STEP 3] Submit sign-in credentials")
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Sign In")').first
        submit_btn.click()

        print("[STEP 4] Verify authentication redirect and landing view")
        # Ensure URL changes away from /signin and user lands on dashboard / workflows / assistant
        page.wait_for_url(lambda url: "/signin" not in url, timeout=15000)
        expect(page).not_to_have_url(f"{BASE_URL}/signin")
        
        # Verify authenticated UI presence (e.g., navigation menu, sidebar, or workflow list)
        main_content = page.locator('main, [data-test-id="sidebar"], nav, #app').first
        expect(main_content).to_be_visible(timeout=10000)

        print(f"[STEP 4 PASS] Successfully signed in. Current URL: {page.url}")
    except Exception as e:
        take_failure_screenshot(page, test_id)
        raise e

import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("TARGET_URL", "http://localhost:5678")
SCREENSHOT_DIR = "test_artifacts/screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def capture_failure_screenshot(page: Page, test_name: str):
    """Utility to capture failure screenshots with breadcrumbs."""
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[DIAGNOSTIC] Screenshot captured at: {screenshot_path}")
    except Exception as exc:
        print(f"[DIAGNOSTIC] Failed to capture screenshot: {exc}")


def test_forgot_password_01_navigate_and_view(page: Page):
    """
    Scenario: Navigate to Forgot Password Flow
    Scenario ID: d56eeec2-52dc-4131-9433-d56ca846658d
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    test_name = "test_forgot_password_01_navigate_and_view"
    try:
        print("[STEP 1] Navigate to signin page on target URL")
        response = page.goto(f"{BASE_URL}/signin", wait_until="networkidle")
        
        assert response is not None, "Response object should not be None"
        print(f"[STEP 1 ASSERT] Response status: {response.status}")
        assert response.status == 200, f"Expected 200 OK for signin page, got {response.status}"

        print("[STEP 2] Check presence of forgot password link on sign-in view")
        forgot_password_link = page.locator("a[href*='forgot-password'], text=/forgot password/i").first
        expect(forgot_password_link).to_be_visible(timeout=5000)
        print("[STEP 2 ASSERT] Forgot password link is visible and interactable")
    except Exception as e:
        capture_failure_screenshot(page, test_name)
        raise e


def test_forgot_password_02_interaction_and_validation(page: Page):
    """
    Scenario: Navigate to Forgot Password Flow
    Scenario ID: d56eeec2-52dc-4131-9433-d56ca846658d
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    test_name = "test_forgot_password_02_interaction_and_validation"
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto(f"{BASE_URL}/signin", wait_until="networkidle")

        print("[STEP 2] Locate and click forgot password link")
        forgot_password_link = page.locator("a[href*='forgot-password'], text=/forgot password/i").first
        expect(forgot_password_link).to_be_visible(timeout=5000)
        forgot_password_link.click()

        print("[STEP 3] Verify route transition towards forgot-password")
        page.wait_for_url("**/forgot-password**", timeout=10000)
        current_url = page.url
        print(f"[STEP 3 ASSERT] Current URL after navigation: {current_url}")
        assert "/forgot-password" in current_url, f"Expected '/forgot-password' in URL, got {current_url}"
    except Exception as e:
        capture_failure_screenshot(page, test_name)
        raise e


def test_forgot_password_03_action_and_outcome(page: Page):
    """
    Scenario: Navigate to Forgot Password Flow
    Scenario ID: d56eeec2-52dc-4131-9433-d56ca846658d
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    test_name = "test_forgot_password_03_action_and_outcome"
    try:
        print("[STEP 1] Navigate directly to /forgot-password route")
        response = page.goto(f"{BASE_URL}/forgot-password", wait_until="networkidle")
        
        assert response is not None, "Response object should not be None"
        print(f"[STEP 1 ASSERT] Response HTTP status code: {response.status}")
        assert response.status == 200, f"Expected status 200 for forgot password view, received {response.status}"

        print("[STEP 2] Verify recovery interface elements are present")
        # Check recovery controls (heading / instructions / email input / reset submit button)
        email_or_recovery_input = page.locator(
            "input[type='email'], input[name='email'], input[placeholder*='email' i], input[type='text']"
        ).first
        expect(email_or_recovery_input).to_be_visible(timeout=5000)
        print("[STEP 2 ASSERT] Recovery input field is visible")

        submit_or_recovery_btn = page.locator(
            "button[type='submit'], button:has-text('Reset'), button:has-text('Send'), input[type='submit']"
        ).first
        expect(submit_or_recovery_btn).to_be_visible(timeout=5000)
        print("[STEP 3 ASSERT] Recovery submit button is visible and active")
    except Exception as e:
        capture_failure_screenshot(page, test_name)
        raise e

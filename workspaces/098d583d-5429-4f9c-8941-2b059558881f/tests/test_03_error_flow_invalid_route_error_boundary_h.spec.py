import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
INVALID_ROUTE = f"{BASE_URL}/home/workflows/non-existent-qa-route-404"
SCREENSHOT_DIR = "screenshots"


@pytest.fixture(scope="function", autouse=True)
def ensure_screenshot_dir():
    """Ensure directory exists for failure screenshots."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def test_invalid_route_404_01_navigate_and_view(page: Page):
    """
    Scenario: Invalid Route & Error Boundary Handling
    Scenario ID: ba45a752-3280-4ca2-9cb2-8856a48340c7
    Subtest: Initial Navigation & View Render
    Category: error_flow
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "ba45a752_01_navigate_and_view_failure.png")
    try:
        print("[STEP 1] Navigate to non-existent route")
        response = page.goto(INVALID_ROUTE, wait_until="domcontentloaded", timeout=30000)

        print("[STEP 2] Verify response received and page rendered")
        page.wait_for_load_state("networkidle", timeout=10000)

        # Ensure page is not blank and not displaying raw server unhandled stack trace
        body_content = page.locator("body")
        expect(body_content).to_be_visible(timeout=5000)

        raw_error_patterns = ["Traceback (most recent call last)", "Cannot GET /", "Internal Server Error 500", "UnhandledPromiseRejection"]
        page_text = page.inner_text("body")
        for pattern in raw_error_patterns:
            assert pattern not in page_text, f"Raw debug or unhandled server crash detected: '{pattern}'"

        print("[SUCCESS] Page rendered gracefully without raw unhandled server crash.")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_invalid_route_404_02_interaction_and_validation(page: Page):
    """
    Scenario: Invalid Route & Error Boundary Handling
    Scenario ID: ba45a752-3280-4ca2-9cb2-8856a48340c7
    Subtest: Interaction & Input Validation
    Category: error_flow
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "ba45a752_02_validation_failure.png")
    try:
        print("[STEP 1] Navigate to invalid route for element validation")
        page.goto(INVALID_ROUTE, wait_until="networkidle", timeout=30000)

        print("[STEP 2] Check for user-friendly 404 message or recovery prompts")
        # Check for 404 text, page not found message, or navigation back to home/signin
        error_indicators = page.locator(
            "text=404, text=/page not found/i, text=/not found/i, text=/looks like you're lost/i, text=/doesn't exist/i, text=/workflows/i, text=/sign in/i"
        )
        expect(error_indicators.first).to_be_visible(timeout=10000)

        print("[STEP 3] Verify presence of safe recovery link or button")
        recovery_element = page.locator(
            "a[href*='/home'], a[href*='/signin'], a[href='/'], button:has-text('Home'), button:has-text('Go back'), a:has-text('Home'), a:has-text('Workflows')"
        )
        expect(recovery_element.first).to_be_visible(timeout=5000)

        print("[SUCCESS] Error boundary / 404 UI indicators and recovery options validated.")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_invalid_route_404_03_action_and_outcome(page: Page):
    """
    Scenario: Invalid Route & Error Boundary Handling
    Scenario ID: ba45a752-3280-4ca2-9cb2-8856a48340c7
    Subtest: Complete Action & Final Verification
    Category: error_flow
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "ba45a752_03_action_and_outcome_failure.png")
    try:
        print("[STEP 1] Navigate to invalid route")
        page.goto(INVALID_ROUTE, wait_until="networkidle", timeout=30000)

        print("[STEP 2] Click recovery navigation element (Home / Return / Workflows)")
        recovery_element = page.locator(
            "a[href*='/home'], a[href*='/signin'], a[href='/'], button:has-text('Home'), button:has-text('Go back'), a:has-text('Home'), a:has-text('Workflows'), a:has-text('Sign In')"
        ).first

        expect(recovery_element).to_be_visible(timeout=5000)
        recovery_element.click()

        print("[STEP 3] Verify navigation back to safe application state")
        page.wait_for_load_state("networkidle", timeout=10000)

        # Expected to land on valid route (such as /signin, /home, /workflows, or root /)
        current_url = page.url
        assert "non-existent-qa-route-404" not in current_url, f"Failed to navigate away from invalid route: {current_url}"

        # Assert body is interactive and rendered
        expect(page.locator("body")).to_be_visible()

        print(f"[SUCCESS] Recovered safely from invalid route. Current URL: {current_url}")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {exc}. Screenshot saved to {screenshot_path}")
        raise

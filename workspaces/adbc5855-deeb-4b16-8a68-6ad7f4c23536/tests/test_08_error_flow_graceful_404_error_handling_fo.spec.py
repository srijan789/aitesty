import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def login_user(page: Page) -> None:
    """Helper function to perform login if not already authenticated."""
    page.goto(f"{BASE_URL}/signin")
    # If already logged in or redirected to workflows/home
    if "/signin" not in page.url:
        return

    # Check for email/username input
    email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[type="text"]').first
    password_input = page.locator('input[type="password"]').first
    submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first

    if email_input.is_visible(timeout=3000):
        email_input.fill("srijan.psn@gmail.com")
        password_input.fill("Password1")
        submit_btn.click()
        page.wait_for_load_state("networkidle")


def capture_failure_screenshot(page: Page, test_name: str) -> None:
    """Helper to capture screenshot on failure."""
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"[DIAGNOSTIC] Screenshot captured at: {screenshot_path}")


def test_invalid_route_404_01_navigate_and_view(page: Page):
    """
    Scenario: Graceful 404 Error Handling for Invalid Routes
    Scenario ID: c2c06045-d468-433f-b56e-249c394dc819
    Subtest: 01 Navigate to Invalid Route and Verify 404 View
    Category: error_flow
    """
    test_name = "test_invalid_route_404_01_navigate_and_view"
    try:
        print("[STEP 1] Authenticate user session")
        login_user(page)

        print("[STEP 2] Navigate to non-existent route 'http://localhost:5678/non-existent-route-404'")
        page.goto(f"{BASE_URL}/non-existent-route-404")
        page.wait_for_load_state("domcontentloaded")

        print("[STEP 3] Verify 404 error page renders without blank screen crash")
        # Check for 404 indicator or error messaging or go-back button
        error_indicator = page.locator('text=/404|Page not found|Not Found|Error/i').first
        expect(error_indicator).to_be_visible(timeout=5000)

        # Ensure page content is non-empty
        body_text = page.locator("body").inner_text()
        assert len(body_text.strip()) > 0, "Page rendered empty white screen on 404 route"
        print("[STEP 4] 404 view rendered cleanly with informative message")

    except Exception as e:
        capture_failure_screenshot(page, test_name)
        print(f"[FAILURE] {test_name} failed: {e}")
        raise


def test_invalid_route_404_02_interaction_and_validation(page: Page):
    """
    Scenario: Graceful 404 Error Handling for Invalid Routes
    Scenario ID: c2c06045-d468-433f-b56e-249c394dc819
    Subtest: 02 Validate Go Back Action on 404 Page
    Category: error_flow
    """
    test_name = "test_invalid_route_404_02_interaction_and_validation"
    try:
        print("[STEP 1] Authenticate user session and navigate to invalid route")
        login_user(page)
        page.goto(f"{BASE_URL}/non-existent-route-404")
        page.wait_for_load_state("domcontentloaded")

        print("[STEP 2] Locate 'Go back' or home return action button")
        go_back_btn = page.locator('button:has-text("Go back"), a:has-text("Go back"), button:has-text("Back"), a:has-text("Back"), button:has-text("Home"), a:has-text("Home")').first
        expect(go_back_btn).to_be_visible(timeout=5000)
        expect(go_back_btn).to_be_enabled()
        print("[STEP 3] 'Go back' navigation option is visible and actionable")

    except Exception as e:
        capture_failure_screenshot(page, test_name)
        print(f"[FAILURE] {test_name} failed: {e}")
        raise


def test_invalid_route_404_03_action_and_outcome(page: Page):
    """
    Scenario: Graceful 404 Error Handling for Invalid Routes
    Scenario ID: c2c06045-d468-433f-b56e-249c394dc819
    Subtest: 03 Click Go Back and Return to Valid View
    Category: error_flow
    """
    test_name = "test_invalid_route_404_03_action_and_outcome"
    try:
        print("[STEP 1] Navigate to a valid authenticated view first")
        login_user(page)
        page.goto(f"{BASE_URL}/home")
        page.wait_for_load_state("networkidle")
        initial_valid_url = page.url

        print("[STEP 2] Navigate directly to non-existent route")
        page.goto(f"{BASE_URL}/non-existent-route-404")
        page.wait_for_load_state("domcontentloaded")

        print("[STEP 3] Click on 'Go back' button")
        go_back_btn = page.locator('button:has-text("Go back"), a:has-text("Go back"), button:has-text("Back"), a:has-text("Back"), button:has-text("Home"), a:has-text("Home")').first
        expect(go_back_btn).to_be_visible(timeout=5000)
        go_back_btn.click()
        page.wait_for_load_state("domcontentloaded")

        print("[STEP 4] Verify return to valid route/view")
        # Current URL should no longer be the invalid 404 route
        assert "non-existent-route-404" not in page.url, f"User stayed on 404 route: {page.url}"
        print(f"[STEP 5] Successfully navigated away from 404 page to: {page.url}")

    except Exception as e:
        capture_failure_screenshot(page, test_name)
        print(f"[FAILURE] {test_name} failed: {e}")
        raise

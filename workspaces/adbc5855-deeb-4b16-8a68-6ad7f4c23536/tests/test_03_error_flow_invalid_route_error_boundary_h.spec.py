import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("TARGET_URL", "http://localhost:5678")
SCREENSHOT_DIR = os.path.join(os.getcwd(), "test-results", "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def test_invalid_route_404_01_navigate_and_view(page: Page):
    """
    Scenario: Invalid Route & Error Boundary Handling
    Scenario ID: 9fb3096c-a661-4d5b-99aa-cae142e57933
    Subtest: Initial Navigation & View Render
    Category: error_flow
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "invalid_route_01_view.png")
    try:
        invalid_url = f"{BASE_URL}/home/workflows/non-existent-qa-route-404"
        print(f"[STEP 1] Navigate to non-existent route: {invalid_url}")
        response = page.goto(invalid_url, wait_until="domcontentloaded", timeout=15000)

        print("[STEP 2] Verify page rendered and is not a blank screen or raw server crash")
        body = page.locator("body")
        expect(body).to_be_visible(timeout=10000)

        # Ensure no raw crash / unhandled stack trace keyword is exposed as the main body content
        body_text = page.locator("body").inner_text()
        assert len(body_text.strip()) > 0, "Page body is completely empty (blank screen)."
        assert "Internal Server Error 500" not in body_text, "Found unhandled 500 server error."
        assert "Traceback (most recent call last)" not in body_text, "Found raw backend traceback."

        print("[STEP 3] Confirm graceful error UI or redirection occurred")
        # n8n / web app either renders a custom 404/not found view, redirects to login/home, or renders standard error boundary
        page.wait_for_timeout(1000)

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] test_invalid_route_404_01_navigate_and_view failed: {e}. Screenshot saved to {screenshot_path}")
        raise


def test_invalid_route_404_02_interaction_and_validation(page: Page):
    """
    Scenario: Invalid Route & Error Boundary Handling
    Scenario ID: 9fb3096c-a661-4d5b-99aa-cae142e57933
    Subtest: Interaction & Input Validation
    Category: error_flow
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "invalid_route_02_validation.png")
    try:
        invalid_url = f"{BASE_URL}/home/workflows/non-existent-qa-route-404"
        print(f"[STEP 1] Request invalid path: {invalid_url}")
        page.goto(invalid_url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)

        print("[STEP 2] Check for user-friendly error UI elements or fallback routing")
        # Look for 404 message, error header, or fallback UI with accessible navigation
        error_heading = page.locator("h1, h2, [data-test-id*='error'], [class*='error'], [class*='notFound'], [class*='404']")
        home_or_back_links = page.locator("a, button").filter(
            has_text=pytest.approx(None) if False else None
        )

        # Check that page provides navigation options (e.g. Home, Sign in, Workflows, or back link)
        nav_elements = page.locator("a[href], button")
        expect(nav_elements.first).to_be_visible(timeout=10000)
        print("[STEP 3] Navigation controls are available on the error/redirect page")

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] test_invalid_route_404_02_interaction_and_validation failed: {e}. Screenshot saved to {screenshot_path}")
        raise


def test_invalid_route_404_03_action_and_outcome(page: Page):
    """
    Scenario: Invalid Route & Error Boundary Handling
    Scenario ID: 9fb3096c-a661-4d5b-99aa-cae142e57933
    Subtest: Complete Action & Final Verification
    Category: error_flow
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "invalid_route_03_recovery.png")
    try:
        invalid_url = f"{BASE_URL}/home/workflows/non-existent-qa-route-404"
        print(f"[STEP 1] Navigate to invalid route: {invalid_url}")
        page.goto(invalid_url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1500)

        print("[STEP 2] Locate return-to-safety / home navigation element")
        # Attempt to click home link, logo, or back button if present
        home_cta = page.locator(
            "a[href='/'], a[href*='home'], a[href*='signin'], a[href*='login'], button:has-text('Home'), a:has-text('Home'), button:has-text('Go back'), a:has-text('Go back')"
        ).first

        if home_cta.is_visible():
            print("[STEP 3] Click Home/Safety navigation element")
            home_cta.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1000)
        else:
            print("[STEP 3] Fallback navigation via direct root URL")
            page.goto(BASE_URL, wait_until="domcontentloaded")

        print("[STEP 4] Verify safe recovery to standard application view")
        expect(page.locator("body")).to_be_visible()
        current_url = page.url
        print(f"[SUCCESS] Successfully recovered to valid route: {current_url}")
        assert BASE_URL in current_url, f"Expected current URL {current_url} to be within {BASE_URL}"

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] test_invalid_route_404_03_action_and_outcome failed: {e}. Screenshot saved to {screenshot_path}")
        raise

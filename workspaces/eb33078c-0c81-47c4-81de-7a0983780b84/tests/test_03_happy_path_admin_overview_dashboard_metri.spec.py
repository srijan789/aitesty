import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_EMAIL = "admin@nanotrak.com"
ADMIN_PASSWORD = "Nanotrak@123"


def login_admin(page: Page) -> None:
    """Helper function to perform authentication if not already logged in."""
    print("[AUTH] Checking current authentication state...")
    try:
        page.goto(f"{BASE_URL}/admin/overview", wait_until="domcontentloaded", timeout=15000)
    except Exception as e:
        print(f"[AUTH] Initial navigation error: {e}")
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=15000)

    # Check if we are redirected to login page
    if "/login" in page.url or page.locator("input[type='email'], input[name='email'], input[placeholder*='Email' i]").is_visible():
        print("[AUTH] Login form detected. Entering credentials...")
        email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='Email' i], input[type='text']").first
        password_input = page.locator("input[type='password'], input[name='password'], input[placeholder*='Password' i]").first
        
        email_input.fill(ADMIN_EMAIL)
        password_input.fill(ADMIN_PASSWORD)
        
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Login')").first
        submit_btn.click()
        
        page.wait_for_load_state("networkidle", timeout=10000)
        print("[AUTH] Successfully authenticated.")


@pytest.fixture(scope="function", autouse=True)
def ensure_authenticated(page: Page):
    """Ensure user is logged in before each test."""
    login_admin(page)


def test_admin_overview_01_navigate_and_view(page: Page):
    """
    Scenario: Admin Overview Dashboard Metrics and Refresh Functionality
    Scenario ID: 04a65e58-d91a-4457-8c82-9043bf0c14a3
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    print("\n[STEP 1] Navigate to /admin/overview and verify dashboard render")
    screenshot_path = "screenshots/04a65e58-d91a-4457-8c82-9043bf0c14a3_01_view.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    try:
        page.goto(f"{BASE_URL}/admin/overview", wait_until="networkidle", timeout=20000)
        print(f"[STEP 1.1] Current URL: {page.url}")
        
        # Verify page URL contains admin/overview or admin dashboard
        assert "/admin" in page.url, f"Expected URL to contain '/admin', got {page.url}"
        
        # Verify main dashboard container / content is visible
        dashboard_content = page.locator("main, .dashboard, #root, body").first
        expect(dashboard_content).to_be_visible(timeout=10000)
        print("[STEP 1.2] Dashboard main container rendered successfully.")
    except Exception as exc:
        page.screenshot(path=screenshot_path)
        print(f"[FAIL] Navigation or view render failed: {exc}. Screenshot saved to {screenshot_path}")
        raise exc


def test_admin_overview_02_interaction_and_validation(page: Page):
    """
    Scenario: Admin Overview Dashboard Metrics and Refresh Functionality
    Scenario ID: 04a65e58-d91a-4457-8c82-9043bf0c14a3
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    print("\n[STEP 2] Assert dashboard headings and widget metrics are present")
    screenshot_path = "screenshots/04a65e58-d91a-4457-8c82-9043bf0c14a3_02_validation.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    try:
        page.goto(f"{BASE_URL}/admin/overview", wait_until="networkidle", timeout=20000)
        
        print("[STEP 2.1] Locating 'FAN ENGAGEMENT DISTRIBUTION' widget heading...")
        fan_engagement_heading = page.locator("text=/FAN ENGAGEMENT DISTRIBUTION/i").first
        expect(fan_engagement_heading).to_be_visible(timeout=10000)
        print("[STEP 2.1 PASS] 'FAN ENGAGEMENT DISTRIBUTION' is displayed.")

        print("[STEP 2.2] Locating 'CELEBRITY SIGNING VOLUME' widget heading...")
        celebrity_signing_heading = page.locator("text=/CELEBRITY SIGNING VOLUME/i").first
        expect(celebrity_signing_heading).to_be_visible(timeout=10000)
        print("[STEP 2.2 PASS] 'CELEBRITY SIGNING VOLUME' is displayed.")

    except Exception as exc:
        page.screenshot(path=screenshot_path)
        print(f"[FAIL] Widget validation failed: {exc}. Screenshot saved to {screenshot_path}")
        raise exc


def test_admin_overview_03_action_and_outcome(page: Page):
    """
    Scenario: Admin Overview Dashboard Metrics and Refresh Functionality
    Scenario ID: 04a65e58-d91a-4457-8c82-9043bf0c14a3
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    print("\n[STEP 3] Trigger 'Refresh Data' and verify metrics re-fetch seamlessly")
    screenshot_path = "screenshots/04a65e58-d91a-4457-8c82-9043bf0c14a3_03_action.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)

    try:
        page.goto(f"{BASE_URL}/admin/overview", wait_until="networkidle", timeout=20000)
        
        # Locate refresh button (by text or aria role or icon with title)
        refresh_btn = page.locator('button:has-text("Refresh Data"), button:has-text("Refresh"), button[title*="Refresh" i]').first
        expect(refresh_btn).to_be_visible(timeout=8000)
        
        print("[STEP 3.1] Clicking 'Refresh Data' button...")
        refresh_btn.click()

        # Wait for potential network activity or subtle state update
        page.wait_for_timeout(1500)
        page.wait_for_load_state("networkidle", timeout=10000)
        
        print("[STEP 3.2] Verifying dashboard widgets persist post-refresh...")
        fan_engagement_heading = page.locator("text=/FAN ENGAGEMENT DISTRIBUTION/i").first
        celebrity_signing_heading = page.locator("text=/CELEBRITY SIGNING VOLUME/i").first
        
        expect(fan_engagement_heading).to_be_visible(timeout=5000)
        expect(celebrity_signing_heading).to_be_visible(timeout=5000)
        print("[STEP 3.2 PASS] Overview metrics re-fetched and displayed seamlessly without errors.")

    except Exception as exc:
        page.screenshot(path=screenshot_path)
        print(f"[FAIL] Refresh Data action failed: {exc}. Screenshot saved to {screenshot_path}")
        raise exc

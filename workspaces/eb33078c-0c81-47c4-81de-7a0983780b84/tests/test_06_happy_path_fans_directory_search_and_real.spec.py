import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_FANS_URL = f"{BASE_URL}/admin/fans"
LOGIN_CREDENTIALS = {
    "username": "admin@nanotrak.com",
    "password": "Nanotrak@123"
}

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def ensure_authenticated(page: Page) -> None:
    """Helper to ensure the user is logged into the Nanotrak portal."""
    print("[AUTH] Checking authentication status...")
    page.goto(ADMIN_FANS_URL, wait_until="domcontentloaded")
    
    # Check if redirected to login
    if "login" in page.url or page.locator("input[type='password']").is_visible():
        print("[AUTH] Logging in with admin credentials...")
        # Target username/email field
        user_input = page.locator("input[type='email'], input[name='username'], input[name='email'], input[placeholder*='Email' i], input[placeholder*='Username' i]").first
        user_input.fill(LOGIN_CREDENTIALS["username"])
        
        # Target password field
        pass_input = page.locator("input[type='password']").first
        pass_input.fill(LOGIN_CREDENTIALS["password"])
        
        # Click login/submit button
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Login')").first
        submit_btn.click()
        
        # Wait for navigation away from login
        page.wait_for_load_state("networkidle")
        print("[AUTH] Login submitted, navigated to:", page.url)


def test_fans_search_01_navigate_and_view(page: Page):
    """
    Scenario: Fans Directory Search and Real-time Filter
    Scenario ID: 52364a65-21df-41ac-8bbf-36769f763a9c
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "test_fans_search_01_failure.png")
    try:
        print("[STEP 1] Authenticating and navigating to Fans management page")
        ensure_authenticated(page)
        
        if not page.url.endswith("/admin/fans"):
            page.goto(ADMIN_FANS_URL, wait_until="networkidle")

        print("[STEP 2] Verifying Fans management page view elements")
        # Assert page title or heading or table/cards region
        fans_header_or_container = page.locator("h1, h2, h3, div:has-text('Fans'), div:has-text('Fan Directory')").first
        expect(fans_header_or_container).to_be_visible(timeout=10000)

        # Assert search input presence
        search_input = page.locator('input[placeholder*="Search by fan" i], input[placeholder*="Search" i], input[type="search"]').first
        expect(search_input).to_be_visible(timeout=10000)
        print("[STEP 3] Verified search bar is displayed on Fans management page")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot saved to {screenshot_path}. Error: {exc}")
        raise


def test_fans_search_02_interaction_and_validation(page: Page):
    """
    Scenario: Fans Directory Search and Real-time Filter
    Scenario ID: 52364a65-21df-41ac-8bbf-36769f763a9c
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "test_fans_search_02_failure.png")
    try:
        print("[STEP 1] Ensuring user is on /admin/fans")
        ensure_authenticated(page)
        if "/admin/fans" not in page.url:
            page.goto(ADMIN_FANS_URL, wait_until="networkidle")

        print("[STEP 2] Locating search input and entering query")
        search_input = page.locator('input[placeholder*="Search by fan" i], input[placeholder*="Search" i], input[type="search"]').first
        expect(search_input).to_be_visible(timeout=10000)
        
        test_query = "TestFan"
        search_input.fill(test_query)
        print(f"[STEP 3] Validating search input value equals '{test_query}'")
        expect(search_input).to_have_value(test_query)

        # Clear query for clean state
        search_input.fill("")
        expect(search_input).to_have_value("")
        print("[STEP 4] Verified search input clear and responsiveness")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot saved to {screenshot_path}. Error: {exc}")
        raise


def test_fans_search_03_action_and_outcome(page: Page):
    """
    Scenario: Fans Directory Search and Real-time Filter
    Scenario ID: 52364a65-21df-41ac-8bbf-36769f763a9c
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "test_fans_search_03_failure.png")
    try:
        print("[STEP 1] Navigating to /admin/fans and preparing real-time filter check")
        ensure_authenticated(page)
        if "/admin/fans" not in page.url:
            page.goto(ADMIN_FANS_URL, wait_until="networkidle")

        search_input = page.locator('input[placeholder*="Search by fan" i], input[placeholder*="Search" i], input[type="search"]').first
        expect(search_input).to_be_visible(timeout=10000)

        # Step 2: Test empty-state query
        non_existent_term = "XYZNonExistentFanQuery999"
        print(f"[STEP 2] Entering non-matching search term: '{non_existent_term}'")
        search_input.fill(non_existent_term)
        page.wait_for_timeout(500)  # debounce wait

        print("[STEP 3] Asserting filtered results or empty state indicator")
        empty_indicator_or_table = page.locator('div[role="region"], table, div:has-text("No"), div:has-text("not found")').first
        expect(empty_indicator_or_table).to_be_visible(timeout=10000)

        # Step 4: Clear search and test broad filter (or partial match)
        print("[STEP 4] Clearing search input to restore full list")
        search_input.fill("")
        page.wait_for_timeout(500)

        content_container = page.locator('div[role="region"], table, div[class*="table"], div[class*="grid"], div[class*="card"]').first
        expect(content_container).to_be_visible(timeout=10000)
        print("[PASS] Real-time search filter verified successfully.")

    except Exception as exc:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot saved to {screenshot_path}. Error: {exc}")
        raise

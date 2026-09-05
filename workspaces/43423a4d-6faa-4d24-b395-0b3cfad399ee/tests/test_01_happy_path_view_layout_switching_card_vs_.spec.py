import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net"
LOGIN_URL = f"{BASE_URL}/sso/login"
USERNAME = "user-3-Team10@velogent.com"
PASSWORD = "F@@OLwY16C"


def login_user(page: Page, target_path: str = "/agentflows") -> None:
    """Helper to authenticate user via SSO login and navigate to target path."""
    print(f"[AUTH] Navigating to SSO login: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="networkidle")

    # Check if already authenticated or on login form
    if "/sso/login" in page.url or page.locator('input[type="password"]').is_visible():
        print("[AUTH] Filling login credentials")
        user_input = page.locator('input[name="username"], input[placeholder*="username" i], input[type="text"], input[type="email"]').first
        expect(user_input).to_be_visible(timeout=10000)
        user_input.fill(USERNAME)

        pass_input = page.locator('input[name="password"], input[type="password"]').first
        expect(pass_input).to_be_visible(timeout=5000)
        pass_input.fill(PASSWORD)

        sign_in_btn = page.locator('button:has-text("Sign in"), button[type="submit"]').first
        sign_in_btn.click()

        print("[AUTH] Submitted credentials, waiting for navigation")
        page.wait_for_load_state("networkidle")

    # Navigate to target path if not already there
    target_url = f"{BASE_URL}{target_path}" if not target_path.startswith("http") else target_path
    if not page.url.startswith(target_url):
        print(f"[AUTH] Navigating directly to target URL: {target_url}")
        page.goto(target_url, wait_until="networkidle")

    page.wait_for_timeout(1000)


def test_view_layout_switching_01_navigate_and_view(page: Page):
    """
    Scenario: View Layout Switching (Card vs List View)
    Scenario ID: 15195c57-9d52-4078-b16c-37ed8d4bb781
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        print("[STEP 1] Authenticate and navigate to '/agentflows'")
        login_user(page, target_path="/agentflows")

        print("[STEP 2] Verify Agentflows view is loaded and layout toggles are present")
        expect(page).not_to_have_url(f"{BASE_URL}/sso/login")
        
        # Verify page header or content exists
        header = page.locator('h1, h2, [data-testid*="header"], div:has-text("Agentflows")').first
        expect(header).to_be_visible(timeout=10000)

        # Verify layout toggle controls (list/card or grid buttons)
        list_toggle = page.locator('button:has-text("list"), button[aria-label*="list" i], button[title*="list" i], [data-testid*="list-view"]').first
        card_toggle = page.locator('button:has-text("card"), button:has-text("grid"), button[aria-label*="card" i], button[aria-label*="grid" i], [data-testid*="grid-view"]').first

        is_list_visible = list_toggle.is_visible()
        is_card_visible = card_toggle.is_visible()
        print(f"[VERIFY] Layout toggle controls detected: list={is_list_visible}, card/grid={is_card_visible}")
        assert is_list_visible or is_card_visible or page.locator('button svg').count() > 0, "Layout toggle buttons should be present on the page"

    except Exception as exc:
        screenshot_path = os.path.join(screenshot_dir, "failure_layout_switching_01.png")
        page.screenshot(path=screenshot_path)
        print(f"[FAILURE] Subtest 01 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_view_layout_switching_02_interaction_and_validation(page: Page):
    """
    Scenario: View Layout Switching (Card vs List View)
    Scenario ID: 15195c57-9d52-4078-b16c-37ed8d4bb781
    Subtest: Interaction & Input Validation (Switch to List View)
    Category: happy_path
    """
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        print("[STEP 1] Authenticate and navigate to '/agentflows'")
        login_user(page, target_path="/agentflows")

        print("[STEP 2] Click on List layout view button")
        list_toggle = page.locator('button:has-text("list"), button[aria-label*="list" i], button[title*="list" i], [data-testid*="list-view"]').first
        expect(list_toggle).to_be_visible(timeout=10000)
        list_toggle.click()
        page.wait_for_timeout(500)

        print("[STEP 3] Assert layout renders items in list/table format")
        # In list mode, verify table, list items, or row containers are present
        list_container = page.locator('table, tbody, [role="table"], [role="row"], .list-view, div[class*="list"]').first
        expect(list_container).to_be_visible(timeout=5000)
        print("[PASS] Successfully switched to list layout view")

    except Exception as exc:
        screenshot_path = os.path.join(screenshot_dir, "failure_layout_switching_02.png")
        page.screenshot(path=screenshot_path)
        print(f"[FAILURE] Subtest 02 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_view_layout_switching_03_action_and_outcome(page: Page):
    """
    Scenario: View Layout Switching (Card vs List View)
    Scenario ID: 15195c57-9d52-4078-b16c-37ed8d4bb781
    Subtest: Complete Action & Final Verification (Toggle Between List and Card)
    Category: happy_path
    """
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    try:
        print("[STEP 1] Authenticate and navigate to '/agentflows'")
        login_user(page, target_path="/agentflows")

        print("[STEP 2] Switch to List layout view")
        list_toggle = page.locator('button:has-text("list"), button[aria-label*="list" i], button[title*="list" i], [data-testid*="list-view"]').first
        expect(list_toggle).to_be_visible(timeout=10000)
        list_toggle.click()
        page.wait_for_timeout(500)

        print("[STEP 3] Switch back to Card/Grid layout view")
        card_toggle = page.locator('button:has-text("card"), button:has-text("grid"), button[aria-label*="card" i], button[aria-label*="grid" i], [data-testid*="grid-view"], [data-testid*="card-view"]').first
        expect(card_toggle).to_be_visible(timeout=10000)
        card_toggle.click()
        page.wait_for_timeout(500)

        print("[STEP 4] Assert layout renders items in card grid format without errors")
        card_container = page.locator('.grid, [role="grid"], div[class*="grid"], div[class*="card"], [data-testid*="card"]').first
        expect(card_container).to_be_visible(timeout=5000)
        print("[PASS] Successfully toggled between card and list layout smoothly")

    except Exception as exc:
        screenshot_path = os.path.join(screenshot_dir, "failure_layout_switching_03.png")
        page.screenshot(path=screenshot_path)
        print(f"[FAILURE] Subtest 03 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise

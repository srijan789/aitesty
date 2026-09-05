import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_EMAIL = "admin@nanotrak.com"
ADMIN_PASSWORD = "Nanotrak@123"
SCREENSHOT_DIR = "test-results/screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def test_admin_auth_valid_01_navigate_and_view(page: Page):
    """
    Scenario: Admin Authentication with Valid Credentials
    Scenario ID: f6ccf787-d3b0-4ce7-860f-ed8fddbb6259
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "f6ccf787_01_navigate_view_failure.png")
    try:
        print("[STEP 1] Navigate to NanoTrak login page")
        response = page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
        assert response is not None, "Failed to load login page"
        assert response.status < 400, f"Page returned HTTP status {response.status}"

        print("[STEP 2] Verify email input is visible and enabled")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        expect(email_input).to_be_visible(timeout=10000)
        expect(email_input).to_be_enabled()

        print("[STEP 3] Verify password input is visible and enabled")
        password_input = page.locator('input[type="password"], input[name="password"]').first
        expect(password_input).to_be_visible(timeout=5000)
        expect(password_input).to_be_enabled()

        print("[STEP 4] Verify Sign in button is rendered")
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first
        expect(submit_btn).to_be_visible(timeout=5000)

        print("[SUCCESS] Initial view rendered correctly with all required authentication controls.")
    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Initial Navigation & View Render failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_admin_auth_valid_02_interaction_and_validation(page: Page):
    """
    Scenario: Admin Authentication with Valid Credentials
    Scenario ID: f6ccf787-d3b0-4ce7-860f-ed8fddbb6259
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "f6ccf787_02_input_validation_failure.png")
    try:
        print("[STEP 1] Navigate to NanoTrak login page")
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")

        print("[STEP 2] Populate email input field")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        expect(email_input).to_be_visible(timeout=10000)
        email_input.fill(ADMIN_EMAIL)
        expect(email_input).to_have_value(ADMIN_EMAIL)

        print("[STEP 3] Populate password input field")
        password_input = page.locator('input[type="password"], input[name="password"]').first
        expect(password_input).to_be_visible(timeout=5000)
        password_input.fill(ADMIN_PASSWORD)
        expect(password_input).to_have_value(ADMIN_PASSWORD)

        print("[STEP 4] Verify submit button is clickable and active")
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first
        expect(submit_btn).to_be_enabled()

        print("[SUCCESS] Credentials entered successfully and inputs verified.")
    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Interaction & Input Validation failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_admin_auth_valid_03_action_and_outcome(page: Page):
    """
    Scenario: Admin Authentication with Valid Credentials
    Scenario ID: f6ccf787-d3b0-4ce7-860f-ed8fddbb6259
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    screenshot_path = os.path.join(SCREENSHOT_DIR, "f6ccf787_03_action_outcome_failure.png")
    try:
        print("[STEP 1] Navigate to NanoTrak login page")
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")

        print("[STEP 2] Fill in valid admin credentials")
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]').first
        password_input = page.locator('input[type="password"], input[name="password"]').first
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first

        email_input.fill(ADMIN_EMAIL)
        password_input.fill(ADMIN_PASSWORD)

        print("[STEP 3] Click Sign in button and wait for navigation")
        submit_btn.click()

        print("[STEP 4] Verify redirection away from login page and towards admin dashboard")
        page.wait_for_url(lambda url: "/admin" in url or "/overview" in url or "/dashboard" in url, timeout=15000)

        print(f"[INFO] Landed on URL: {page.url}")
        assert "/admin" in page.url or "/overview" in page.url or "/dashboard" in page.url, (
            f"Expected redirection to admin route, but stayed at: {page.url}"
        )

        print("[STEP 5] Verify admin interface elements and profile information are visible")
        # Check for admin profile indicator, navigation items, or dashboard overview content
        admin_profile_or_nav = page.locator(
            'text="Admin NanoTrak", text="Admin", text="Overview", text="Dashboard", [data-testid="admin-profile"], [aria-label*="Admin" i]'
        ).first
        expect(admin_profile_or_nav).to_be_visible(timeout=10000)

        print("[SUCCESS] Admin authentication succeeded with full dashboard verification.")
    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Complete Action & Final Verification failed: {e}. Screenshot captured at {screenshot_path}")
        raise

import os
import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_EMAIL = "admin@nanotrak.com"
ADMIN_PASSWORD = "Nanotrak@123"


def test_admin_login_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Admin User Login with Valid Credentials
    Scenario ID: 021a81e7-d02e-43e9-9d00-1d8c466926a8
    Subtest: Initial Navigation & Login View Render
    Category: happy_path
    """
    print("\n[STEP 1] Navigate to Nanotrak login page")
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        
        print("[STEP 2] Verify login page view and critical UI elements are rendered")
        # Check email input
        email_input = page.locator('input[type="email"], input[name="email"], input[id="email"], input[placeholder*="email" i]').first
        expect(email_input).to_be_visible(timeout=10000)
        
        # Check password input
        password_input = page.locator('input[type="password"], input[name="password"], input[id="password"]').first
        expect(password_input).to_be_visible(timeout=10000)
        
        # Check submit/sign in button
        submit_btn = page.locator('button:has-text("Sign in"), button:has-text("Sign In"), button:has-text("Login"), button[type="submit"]').first
        expect(submit_btn).to_be_visible(timeout=10000)
        
        print("[STEP 3] Login page rendered successfully with email, password, and sign-in button.")
    except Exception as exc:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = "screenshots/login_01_navigate_fail.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Initial view render failed: {exc}. Screenshot captured at {screenshot_path}")
        raise exc


def test_admin_login_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Admin User Login with Valid Credentials
    Scenario ID: 021a81e7-d02e-43e9-9d00-1d8c466926a8
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    print("\n[STEP 1] Navigate to login page for input interaction")
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        
        email_input = page.locator('input[type="email"], input[name="email"], input[id="email"], input[placeholder*="email" i]').first
        password_input = page.locator('input[type="password"], input[name="password"], input[id="password"]').first
        
        print(f"[STEP 2] Fill admin email: {ADMIN_EMAIL}")
        email_input.fill(ADMIN_EMAIL)
        expect(email_input).to_have_value(ADMIN_EMAIL)
        
        print("[STEP 3] Fill admin password securely")
        password_input.fill(ADMIN_PASSWORD)
        expect(password_input).to_have_value(ADMIN_PASSWORD)
        
        submit_btn = page.locator('button:has-text("Sign in"), button:has-text("Sign In"), button:has-text("Login"), button[type="submit"]').first
        expect(submit_btn).to_be_enabled()
        print("[STEP 4] Inputs populated and validated successfully.")
    except Exception as exc:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = "screenshots/login_02_interaction_fail.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Interaction and validation failed: {exc}. Screenshot captured at {screenshot_path}")
        raise exc


def test_admin_login_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Admin User Login with Valid Credentials
    Scenario ID: 021a81e7-d02e-43e9-9d00-1d8c466926a8
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    print("\n[STEP 1] Navigate to login page")
    try:
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        
        print(f"[STEP 2] Fill credentials for user: {ADMIN_EMAIL}")
        email_input = page.locator('input[type="email"], input[name="email"], input[id="email"], input[placeholder*="email" i]').first
        password_input = page.locator('input[type="password"], input[name="password"], input[id="password"]').first
        submit_btn = page.locator('button:has-text("Sign in"), button:has-text("Sign In"), button:has-text("Login"), button[type="submit"]').first
        
        email_input.fill(ADMIN_EMAIL)
        password_input.fill(ADMIN_PASSWORD)
        
        print("[STEP 3] Click Sign in button and await authentication response")
        submit_btn.click()
        
        print("[STEP 4] Assert redirection to admin overview dashboard")
        page.wait_for_url(re.compile(r".*/(admin(/overview)?)?"), timeout=15000)
        
        # Verify page URL contains admin or overview
        expect(page).to_have_url(re.compile(r".*/admin.*|.*/overview.*"), timeout=15000)
        
        print("[STEP 5] Assert presence of admin overview dashboard elements")
        overview_header = page.locator('h1, h2, h3, div:has-text("OVERVIEW"), div:has-text("Admin")').filter(has_text=re.compile(r"overview|admin", re.IGNORECASE)).first
        expect(overview_header).to_be_visible(timeout=15000)
        
        print("[STEP 6] Authentication successful: Admin user is redirected to the overview dashboard.")
    except Exception as exc:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = "screenshots/login_03_action_outcome_fail.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Login action and outcome verification failed: {exc}. Screenshot captured at {screenshot_path}")
        raise exc

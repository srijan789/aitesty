import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("BASE_URL", "http://localhost:5678")
AUTH_USER = "srijan.psn@gmail.com"
AUTH_PASS = "Password1"


def login_if_needed(page: Page) -> None:
    """Helper to authenticate user into the application if not already logged in."""
    page.goto(f"{BASE_URL}/signin")
    page.wait_for_load_state("domcontentloaded")
    
    # Check if login form is displayed
    email_input = page.locator("input[name='email'], input[type='email'], input[data-test-id='signin-email-input']")
    if email_input.is_visible(timeout=3000):
        print(f"[AUTH] Logging in with user {AUTH_USER}")
        email_input.fill(AUTH_USER)
        
        password_input = page.locator("input[name='password'], input[type='password'], input[data-test-id='signin-password-input']")
        password_input.fill(AUTH_PASS)
        
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')")
        submit_btn.click()
        page.wait_for_load_state("networkidle")


def test_settings_dashboard_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Access Settings Configuration Dashboard
    Scenario ID: a254857e-b671-4473-992a-a03cedf7675f
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticate user and navigate to Settings page")
        login_if_needed(page)

        print("[STEP 2] Navigate directly to /settings")
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_load_state("networkidle")

        print("[STEP 3] Verify Settings dashboard view rendered without 500 error or blank screen")
        # Ensure page content is present and not an error screen
        body_text = page.locator("body")
        expect(body_text).not_to_contain_text("Internal Server Error")
        expect(body_text).not_to_contain_text("500")

        # Verify main settings container or heading is visible
        settings_view = page.locator("div[class*='settings'], main, [data-test-id='settings-container'], h1, h2").first
        expect(settings_view).to_be_visible()
        print("[STEP 4] Settings dashboard navigation and initial view render verified successfully")

    except Exception as e:
        screenshot_path = "failure_settings_01_navigate_and_view.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 01 failed: {str(e)}. Screenshot saved to {screenshot_path}")
        raise


def test_settings_dashboard_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Access Settings Configuration Dashboard
    Scenario ID: a254857e-b671-4473-992a-a03cedf7675f
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticate user and navigate to Settings page")
        login_if_needed(page)
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_load_state("networkidle")

        print("[STEP 2] Assert settings sub-links and navigation tabs are present")
        # Assert on settings sidebar / navigation links
        users_link = page.locator("a[href*='/settings/users'], a:has-text('Users')").first
        expect(users_link).to_be_visible()

        # Check for other standard settings sub-links
        settings_nav = page.locator("nav, aside, [class*='sidebar'], [class*='menu']")
        expect(settings_nav.first).to_be_visible()

        print("[STEP 3] Validate Users navigation link is clickable and accessible")
        expect(users_link).to_be_enabled()
        print("[STEP 4] Interaction and link validation successful")

    except Exception as e:
        screenshot_path = "failure_settings_02_interaction_and_validation.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 02 failed: {str(e)}. Screenshot saved to {screenshot_path}")
        raise


def test_settings_dashboard_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Access Settings Configuration Dashboard
    Scenario ID: a254857e-b671-4473-992a-a03cedf7675f
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticate user and navigate to Settings page")
        login_if_needed(page)
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_load_state("networkidle")

        print("[STEP 2] Click Users sub-link to verify settings section routing")
        users_link = page.locator("a[href*='/settings/users'], a:has-text('Users')").first
        users_link.click()
        page.wait_for_load_state("networkidle")

        print("[STEP 3] Verify URL updated to /settings/users and Users management section renders")
        expect(page).to_have_url(f"{BASE_URL}/settings/users")
        
        # Verify users section content loads
        users_header_or_content = page.locator("h1, h2, div:has-text('Users'), button:has-text('Invite')").first
        expect(users_header_or_content).to_be_visible()
        print("[STEP 4] Settings navigation outcome and route verification completed successfully")

    except Exception as e:
        screenshot_path = "failure_settings_03_action_and_outcome.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 03 failed: {str(e)}. Screenshot saved to {screenshot_path}")
        raise

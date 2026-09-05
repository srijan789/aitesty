import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5678")
AUTH_USER = os.environ.get("AUTH_USER", "srijan.psn@gmail.com")
AUTH_PASS = os.environ.get("AUTH_PASS", "Password1")


def login_if_needed(page: Page) -> None:
    """Helper to ensure user is authenticated before running tests."""
    page.goto(f"{BASE_URL}/signin", wait_until="networkidle")
    
    # Check if already authenticated or on signin screen
    if "/signin" in page.url or page.locator("input[name='email'], input[type='email'], input[name='username']").count() > 0:
        try:
            email_input = page.locator("input[name='email'], input[type='email'], input[name='username'], [data-test-id='signin-email-input']").first
            if email_input.is_visible(timeout=3000):
                email_input.fill(AUTH_USER)
                password_input = page.locator("input[name='password'], input[type='password'], [data-test-id='signin-password-input']").first
                password_input.fill(AUTH_PASS)
                
                submit_button = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in'), [data-test-id='signin-button']").first
                submit_button.click()
                page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"[AUTH] Login attempt finished or bypassed: {e}")


def test_ai_assistant_onboarding_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: AI Assistant Onboarding and Dismissal
    Scenario ID: 9bedf1a3-d6ff-4af9-86d5-f892c1d997f3
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticating user and navigating to /assistant")
        login_if_needed(page)
        
        page.goto(f"{BASE_URL}/assistant", wait_until="networkidle")
        
        print("[STEP 2] Verifying AI Assistant onboarding view rendered")
        # Check that page or modal with assistant prompt appears
        assistant_container = page.locator("text=/AI Assistant|Assistant/i, [data-test-id='assistant-onboarding'], button:has-text('Set up later in Settings'), button:has-text('Get started')").first
        expect(assistant_container).to_be_visible(timeout=10000)
        print("[SUCCESS] AI Assistant onboarding view loaded successfully.")
    except Exception as exc:
        screenshot_path = "failed_ai_assistant_01_navigate_and_view.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed at step with error: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_ai_assistant_onboarding_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: AI Assistant Onboarding and Dismissal
    Scenario ID: 9bedf1a3-d6ff-4af9-86d5-f892c1d997f3
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    try:
        print("[STEP 1] Authenticating user and navigating to /assistant")
        login_if_needed(page)
        page.goto(f"{BASE_URL}/assistant", wait_until="networkidle")
        
        print("[STEP 2] Validating onboarding action options exist")
        setup_later_btn = page.locator("button:has-text('Set up later in Settings'), button:has-text('Set up later'), button:has-text('Later')").first
        expect(setup_later_btn).to_be_visible(timeout=10000)
        
        # Verify alternative action or description is present
        banner_or_action = page.locator("button:has-text('Get started'), button:has-text('Set up now'), text=/Set up later in Settings/i").first
        expect(banner_or_action).to_be_visible(timeout=5000)
        print("[SUCCESS] Onboarding options validated successfully.")
    except Exception as exc:
        screenshot_path = "failed_ai_assistant_02_interaction_and_validation.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed at step with error: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_ai_assistant_onboarding_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: AI Assistant Onboarding and Dismissal
    Scenario ID: 9bedf1a3-d6ff-4af9-86d5-f892c1d997f3
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigating to /assistant")
        login_if_needed(page)
        page.goto(f"{BASE_URL}/assistant", wait_until="networkidle")
        
        print("[STEP 2] Clicking 'Set up later in Settings' button to dismiss prompt")
        setup_later_btn = page.locator("button:has-text('Set up later in Settings'), button:has-text('Set up later'), [data-test-id='setup-later-button']").first
        expect(setup_later_btn).to_be_visible(timeout=10000)
        setup_later_btn.click()
        
        print("[STEP 3] Verifying dismissal and redirect to workflows view")
        page.wait_for_load_state("networkidle")
        
        # Check redirection to workflows or /home/workflows
        expect(page).to_have_url(r".*(/home/workflows|/workflows|/home).*", timeout=10000)
        
        # Verify workflows page elements or heading is visible
        workflows_indicator = page.locator("text=/Workflows/i, [data-test-id='workflows-list'], [data-test-id='resources-list-item']").first
        expect(workflows_indicator).to_be_visible(timeout=10000)
        print("[SUCCESS] AI Assistant prompt dismissed and redirected to workflows successfully.")
    except Exception as exc:
        screenshot_path = "failed_ai_assistant_03_action_and_outcome.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed at step with error: {exc}. Screenshot saved to {screenshot_path}")
        raise

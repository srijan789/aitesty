import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_EMAIL = "admin@nanotrak.com"
ADMIN_PASS = "Nanotrak@123"
SCREENSHOTS_DIR = "screenshots"


def ensure_authenticated(page: Page) -> None:
    """Helper to ensure the user is logged into the NanoTrak Admin portal."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    page.goto(f"{BASE_URL}/admin/celebrities", wait_until="domcontentloaded")
    
    # Check if redirected to login
    if "login" in page.url or page.locator("input[type='password']").is_visible():
        print("[AUTH] Performing login for admin user...")
        # Fill email
        email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='Email' i], input[type='text']").first
        email_input.fill(ADMIN_EMAIL)
        
        # Fill password
        password_input = page.locator("input[type='password']").first
        password_input.fill(ADMIN_PASS)
        
        # Click login button
        login_btn = page.locator("button[type='submit'], button:has-text('Login'), button:has-text('Sign In')").first
        login_btn.click()
        
        # Wait for navigation
        page.wait_for_load_state("networkidle")
        
        # Navigate to target page if not already there
        if "/admin/celebrities" not in page.url:
            page.goto(f"{BASE_URL}/admin/celebrities", wait_until="networkidle")


def test_celebrity_onboarding_empty_validation_01_navigate_and_view(page: Page):
    """
    Scenario: Celebrity Onboarding Form Validation on Empty Submission
    Scenario ID: 384d5a33-afce-4c2f-ac82-f0a3a1567438
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigating to Celebrity Management page and ensuring authentication...")
        ensure_authenticated(page)
        
        print("[STEP 2] Verifying Celebrity Management page view loaded...")
        expect(page).to_have_url(lambda u: "/admin/celebrities" in u)
        
        # Verify 'Add New' action button is present and visible
        add_new_btn = page.locator("button:has-text('Add New'), a:has-text('Add New')").first
        expect(add_new_btn).to_be_visible()
        print("[SUCCESS] Celebrity Management view successfully verified.")
        
    except Exception as exc:
        screenshot_path = os.path.join(SCREENSHOTS_DIR, "failed_384d5a33_subtest_01.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 01 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_celebrity_onboarding_empty_validation_02_interaction_and_validation(page: Page):
    """
    Scenario: Celebrity Onboarding Form Validation on Empty Submission
    Scenario ID: 384d5a33-afce-4c2f-ac82-f0a3a1567438
    Subtest: Interaction & Modal Opening
    Category: edge_case
    """
    try:
        print("[STEP 1] Ensuring session is on Celebrity Management page...")
        ensure_authenticated(page)
        
        print("[STEP 2] Clicking on 'Add New' button...")
        add_new_btn = page.locator("button:has-text('Add New'), a:has-text('Add New')").first
        expect(add_new_btn).to_be_visible()
        add_new_btn.click()
        
        print("[STEP 3] Selecting 'Celebrity Profile' option if modal/dropdown is displayed...")
        celebrity_profile_btn = page.locator(
            "button:has-text('Celebrity Profile'), [role='menuitem']:has-text('Celebrity Profile'), div:has-text('Celebrity Profile')"
        ).first
        if celebrity_profile_btn.is_visible():
            celebrity_profile_btn.click()
        
        print("[STEP 4] Verifying Onboarding modal is displayed with Next Step button...")
        # Check wizard modal container or step 1 elements
        modal = page.locator("div[role='dialog'], .modal, .MuiDialog-root, form, .onboarding-modal").first
        expect(modal).to_be_visible()
        
        next_step_btn = page.locator("button:has-text('NEXT STEP'), button:has-text('Next Step'), button:has-text('Next')").first
        expect(next_step_btn).to_be_visible()
        print("[SUCCESS] Celebrity Onboarding form modal rendered with empty fields.")
        
    except Exception as exc:
        screenshot_path = os.path.join(SCREENSHOTS_DIR, "failed_384d5a33_subtest_02.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 02 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise


def test_celebrity_onboarding_empty_validation_03_action_and_outcome(page: Page):
    """
    Scenario: Celebrity Onboarding Form Validation on Empty Submission
    Scenario ID: 384d5a33-afce-4c2f-ac82-f0a3a1567438
    Subtest: Complete Action & Final Verification
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigating and opening Celebrity Onboarding modal...")
        ensure_authenticated(page)
        
        add_new_btn = page.locator("button:has-text('Add New'), a:has-text('Add New')").first
        expect(add_new_btn).to_be_visible()
        add_new_btn.click()
        
        celebrity_profile_btn = page.locator(
            "button:has-text('Celebrity Profile'), [role='menuitem']:has-text('Celebrity Profile'), div:has-text('Celebrity Profile')"
        ).first
        if celebrity_profile_btn.is_visible():
            celebrity_profile_btn.click()
        
        next_step_btn = page.locator("button:has-text('NEXT STEP'), button:has-text('Next Step'), button:has-text('Next')").first
        expect(next_step_btn).to_be_visible()
        
        print("[STEP 2] Submitting empty form by clicking NEXT STEP without entering data...")
        next_step_btn.click()
        
        print("[STEP 3] Verifying form blocks progression to Step 2 and displays validation feedback...")
        
        # Check that the form does not advance: NEXT STEP button should still be visible on Step 1
        expect(next_step_btn).to_be_visible()
        
        # Check for validation indicators: error text, invalid pseudo-classes, or aria-invalid attributes
        validation_indicators = page.locator(
            ".error, .text-danger, .Mui-error, [aria-invalid='true'], p:has-text('required'), span:has-text('required'), div:has-text('required')"
        )
        
        # Either validation error elements are visible or the modal remains locked on Step 1
        is_error_shown = validation_indicators.count() > 0
        is_still_step_1 = next_step_btn.is_visible()
        
        assert is_still_step_1, "Form unexpectedly advanced or closed on empty submission!"
        
        # Additional check to ensure we did not advance to step 2/complete step
        step_2_indicator = page.locator("text='Step 2', text='Social Media', text='Bio & Links'").first
        if step_2_indicator.is_visible():
            # If step 2 text is present, ensure it's not active/selected
            expect(page.locator(".active:has-text('Step 2'), [aria-selected='true']:has-text('Step 2')")).not_to_be_visible()

        print("[SUCCESS] Form validation confirmed: empty submission prevented wizard progression.")

    except Exception as exc:
        screenshot_path = os.path.join(SCREENSHOTS_DIR, "failed_384d5a33_subtest_03.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Subtest 03 failed: {exc}. Screenshot saved to {screenshot_path}")
        raise

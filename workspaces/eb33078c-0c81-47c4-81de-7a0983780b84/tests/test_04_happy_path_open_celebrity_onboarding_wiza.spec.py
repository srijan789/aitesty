import pytest
import os
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_USERNAME = "admin@nanotrak.com"
ADMIN_PASSWORD = "Nanotrak@123"
SCREENSHOT_DIR = "screenshots"


def ensure_screenshot_dir():
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def login_if_required(page: Page):
    """Helper function to perform login if redirected to login page."""
    print("[AUTH] Checking authentication state...")
    page.goto(f"{BASE_URL}/admin/celebrities", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    # Check if login form is present
    if "login" in page.url.lower() or page.locator("input[type='password']").is_visible():
        print("[AUTH] Login page detected. Performing authentication...")
        
        email_input = page.locator("input[type='email'], input[name='email'], input[name='username'], input[placeholder*='Email' i], input[placeholder*='Username' i]").first
        password_input = page.locator("input[type='password'], input[name='password'], input[placeholder*='Password' i]").first
        submit_button = page.locator("button[type='submit'], button:has-text('Log In'), button:has-text('Login'), button:has-text('Sign In')").first
        
        email_input.fill(ADMIN_USERNAME)
        password_input.fill(ADMIN_PASSWORD)
        submit_button.click()

        page.wait_for_url("**/admin/**", timeout=15000)
        page.wait_for_load_state("networkidle")
        print("[AUTH] Successfully authenticated.")
    else:
        print("[AUTH] Already authenticated or on admin page.")


def test_open_celebrity_onboarding_wizard_01_navigate_and_view(page: Page):
    """
    Scenario: Open Celebrity Onboarding Wizard Modal
    Scenario ID: 6918dac4-f193-4248-8ca1-cd9dacc6eee3
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    ensure_screenshot_dir()
    try:
        print("[STEP 1] Log in and navigate to Celebrities management directory")
        login_if_required(page)
        
        if not page.url.endswith("/admin/celebrities"):
            page.goto(f"{BASE_URL}/admin/celebrities", wait_until="networkidle")

        print("[STEP 2] Verify Celebrity Management directory is displayed")
        page_header = page.locator("h1, h2, h3, div").filter(has_text="Celebrities").first
        expect(page_header).to_be_visible(timeout=10000)

        print("[STEP 3] Verify 'Add New' action button is present and visible")
        add_new_btn = page.locator("button:has-text('Add New')").first
        expect(add_new_btn).to_be_visible(timeout=10000)
        expect(add_new_btn).to_be_enabled()
        print("[STEP 3 COMPLETED] Directory and 'Add New' button rendered successfully.")

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "failure_01_navigate_and_view.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test 01 failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_open_celebrity_onboarding_wizard_02_interaction_and_validation(page: Page):
    """
    Scenario: Open Celebrity Onboarding Wizard Modal
    Scenario ID: 6918dac4-f193-4248-8ca1-cd9dacc6eee3
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    ensure_screenshot_dir()
    try:
        print("[STEP 1] Navigate to Celebrities management page")
        login_if_required(page)
        if not page.url.endswith("/admin/celebrities"):
            page.goto(f"{BASE_URL}/admin/celebrities", wait_until="networkidle")

        print("[STEP 2] Click on 'Add New' button to open the dropdown menu")
        add_new_btn = page.locator("button:has-text('Add New')").first
        expect(add_new_btn).to_be_visible(timeout=10000)
        add_new_btn.click()

        print("[STEP 3] Verify dropdown displays 'Celebrity Profile' and 'Hardware Pen' options")
        celebrity_profile_opt = page.locator("button:has-text('Celebrity Profile'), div[role='menuitem']:has-text('Celebrity Profile'), a:has-text('Celebrity Profile'), li:has-text('Celebrity Profile')").first
        expect(celebrity_profile_opt).to_be_visible(timeout=5000)

        hardware_pen_opt = page.locator("button:has-text('Hardware Pen'), div[role='menuitem']:has-text('Hardware Pen'), a:has-text('Hardware Pen'), li:has-text('Hardware Pen')").first
        expect(hardware_pen_opt).to_be_visible(timeout=5000)
        print("[STEP 3 COMPLETED] Dropdown options verified.")

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "failure_02_interaction_and_validation.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test 02 failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_open_celebrity_onboarding_wizard_03_action_and_outcome(page: Page):
    """
    Scenario: Open Celebrity Onboarding Wizard Modal
    Scenario ID: 6918dac4-f193-4248-8ca1-cd9dacc6eee3
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    ensure_screenshot_dir()
    try:
        print("[STEP 1] Navigate to Celebrities management page")
        login_if_required(page)
        if not page.url.endswith("/admin/celebrities"):
            page.goto(f"{BASE_URL}/admin/celebrities", wait_until="networkidle")

        print("[STEP 2] Click 'Add New' button")
        add_new_btn = page.locator("button:has-text('Add New')").first
        expect(add_new_btn).to_be_visible(timeout=10000)
        add_new_btn.click()

        print("[STEP 3] Select 'Celebrity Profile' from dropdown menu")
        celebrity_profile_opt = page.locator("button:has-text('Celebrity Profile'), div[role='menuitem']:has-text('Celebrity Profile'), a:has-text('Celebrity Profile'), li:has-text('Celebrity Profile')").first
        expect(celebrity_profile_opt).to_be_visible(timeout=5000)
        celebrity_profile_opt.click()

        print("[STEP 4] Verify Onboard Celebrity wizard modal is displayed")
        modal_header = page.locator("div[role='dialog'], .modal, div[class*='modal']").filter(
            has=page.locator("text=/ONBOARD CELEBRITY|Onboard Celebrity/i")
        ).first
        expect(modal_header).to_be_visible(timeout=10000)

        print("[STEP 5] Verify required onboarding input fields (First Name, Last Name, Email, Handle)")
        first_name_input = page.locator("input[name*='firstName' i], input[placeholder*='First Name' i], input[id*='firstName' i]").first
        last_name_input = page.locator("input[name*='lastName' i], input[placeholder*='Last Name' i], input[id*='lastName' i]").first
        email_input = page.locator("input[type='email'], input[name*='email' i], input[placeholder*='Email' i]").first
        handle_input = page.locator("input[name*='handle' i], input[placeholder*='Handle' i], input[id*='handle' i]").first

        expect(first_name_input).to_be_visible(timeout=5000)
        expect(last_name_input).to_be_visible(timeout=5000)
        expect(email_input).to_be_visible(timeout=5000)
        expect(handle_input).to_be_visible(timeout=5000)

        print("[STEP 5 COMPLETED] All fields in Onboard Celebrity wizard verified successfully.")

    except Exception as e:
        screenshot_path = os.path.join(SCREENSHOT_DIR, "failure_03_action_and_outcome.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test 03 failed: {e}. Screenshot captured at {screenshot_path}")
        raise

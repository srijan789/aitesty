import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_USERNAME = "admin@nanotrak.com"
ADMIN_PASSWORD = "Nanotrak@123"


def login_as_admin(page: Page) -> None:
    """Helper to log in as administrator and ensure session is active."""
    print("[AUTH] Navigating to login page...")
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")

    # If already logged in, skip login flow
    if "/admin" in page.url:
        print("[AUTH] Already logged in.")
        return

    # Check for login inputs
    username_input = page.locator('input[name="username"], input[type="email"], input[placeholder*="Email" i], input[placeholder*="Username" i]').first
    password_input = page.locator('input[name="password"], input[type="password"]').first
    login_btn = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign In")').first

    if username_input.is_visible(timeout=5000):
        print("[AUTH] Submitting login credentials...")
        username_input.fill(ADMIN_USERNAME)
        password_input.fill(ADMIN_PASSWORD)
        login_btn.click()
        page.wait_for_load_state("networkidle")


def navigate_to_celebrities_view(page: Page) -> None:
    """Helper to ensure user is on /admin/celebrities."""
    login_as_admin(page)
    print(f"[NAV] Navigating to {BASE_URL}/admin/celebrities")
    page.goto(f"{BASE_URL}/admin/celebrities")
    page.wait_for_load_state("networkidle")


def test_celebrity_onboarding_modal_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Celebrity Onboarding Modal Rendering and Form Elements
    Scenario ID: c2ce4938-f234-45b3-8400-c7bb4b14612e
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to /admin/celebrities and verify view rendering")
        navigate_to_celebrities_view(page)

        # Assert celebrities management view is loaded
        expect(page).to_have_url(f"{BASE_URL}/admin/celebrities")
        add_new_btn = page.locator('button:has-text("Add New"), [data-testid="add-new-button"]').first
        expect(add_new_btn).to_be_visible(timeout=10000)
        print("[STEP 1] Celebrities management view successfully rendered with 'Add New' action button.")
    except Exception as e:
        screenshot_path = "failure_celebrity_onboarding_01.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[ERROR] Failed in subtest 01: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_celebrity_onboarding_modal_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Celebrity Onboarding Modal Rendering and Form Elements
    Scenario ID: c2ce4938-f234-45b3-8400-c7bb4b14612e
    Subtest: Interaction & Dropdown Menu Trigger
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to celebrities management view")
        navigate_to_celebrities_view(page)

        print("[STEP 2] Click 'Add New' button to open menu")
        add_new_btn = page.locator('button:has-text("Add New"), [data-testid="add-new-button"]').first
        expect(add_new_btn).to_be_visible(timeout=10000)
        add_new_btn.click()

        print("[STEP 3] Verify dropdown options appear")
        celeb_profile_option = page.locator('button:has-text("Celebrity Profile"), [role="menuitem"]:has-text("Celebrity Profile"), text="Celebrity Profile"').first
        expect(celeb_profile_option).to_be_visible(timeout=5000)

        # Also check Hardware Pen or other menu items if present
        hardware_pen_option = page.locator('button:has-text("Hardware Pen"), [role="menuitem"]:has-text("Hardware Pen"), text="Hardware Pen"').first
        if hardware_pen_option.is_visible():
            print("[STEP 3] 'Hardware Pen' option is also visible in dropdown.")
    except Exception as e:
        screenshot_path = "failure_celebrity_onboarding_02.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[ERROR] Failed in subtest 02: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_celebrity_onboarding_modal_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Celebrity Onboarding Modal Rendering and Form Elements
    Scenario ID: c2ce4938-f234-45b3-8400-c7bb4b14612e
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to celebrities management view")
        navigate_to_celebrities_view(page)

        print("[STEP 2] Click on 'Add New' button")
        add_new_btn = page.locator('button:has-text("Add New"), [data-testid="add-new-button"]').first
        expect(add_new_btn).to_be_visible(timeout=10000)
        add_new_btn.click()

        print("[STEP 3] Click on 'Celebrity Profile' option to open modal")
        celeb_profile_option = page.locator('button:has-text("Celebrity Profile"), [role="menuitem"]:has-text("Celebrity Profile"), text="Celebrity Profile"').first
        expect(celeb_profile_option).to_be_visible(timeout=5000)
        celeb_profile_option.click()

        print("[STEP 4] Assert modal header 'ONBOARD CELEBRITY' is displayed")
        modal_header = page.locator('text="ONBOARD CELEBRITY", text="Onboard Celebrity", h2:has-text("Onboard"), h3:has-text("Onboard")').first
        expect(modal_header).to_be_visible(timeout=7000)

        print("[STEP 5] Verify all 8 required onboarding inputs are present")
        # 1. First Name
        first_name_input = page.locator('input[name="firstName"], input[placeholder*="First Name" i], label:has-text("First Name") ~ input, input[id*="first" i]').first
        expect(first_name_input).to_be_visible()

        # 2. Last Name
        last_name_input = page.locator('input[name="lastName"], input[placeholder*="Last Name" i], label:has-text("Last Name") ~ input, input[id*="last" i]').first
        expect(last_name_input).to_be_visible()

        # 3. Username
        username_input = page.locator('input[name="username"], input[placeholder*="Username" i], label:has-text("Username") ~ input').first
        expect(username_input).to_be_visible()

        # 4. Password
        password_input = page.locator('input[name="password"], input[type="password"], input[placeholder*="Password" i], label:has-text("Password") ~ input').first
        expect(password_input).to_be_visible()

        # 5. Email
        email_input = page.locator('input[name="email"], input[type="email"], input[placeholder*="Email" i], label:has-text("Email") ~ input').first
        expect(email_input).to_be_visible()

        # 6. Phone
        phone_input = page.locator('input[name="phone"], input[type="tel"], input[placeholder*="Phone" i], label:has-text("Phone") ~ input').first
        expect(phone_input).to_be_visible()

        # 7. DOB
        dob_input = page.locator('input[name="dob"], input[name="dateOfBirth"], input[type="date"], input[placeholder*="DOB" i], input[placeholder*="Date of Birth" i], label:has-text("DOB") ~ input, label:has-text("Date of Birth") ~ input').first
        expect(dob_input).to_be_visible()

        # 8. Category Selector
        category_selector = page.locator('select[name="category"], select[name="categoryId"], [role="combobox"]:has-text("Category"), div[class*="select"]:has-text("Category"), label:has-text("Category") ~ *').first
        expect(category_selector).to_be_visible()

        # Next Step button
        next_step_btn = page.locator('button:has-text("Next Step"), button:has-text("NEXT STEP"), button:has-text("Next")').first
        expect(next_step_btn).to_be_visible()

        print("[STEP 5] All 8 input fields and the Next Step button are successfully verified in the modal.")
    except Exception as e:
        screenshot_path = "failure_celebrity_onboarding_03.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[ERROR] Failed in subtest 03: {e}. Screenshot captured at {screenshot_path}")
        raise

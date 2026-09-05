import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_USER = "admin@nanotrak.com"
ADMIN_PASS = "Nanotrak@123"


def perform_login_if_needed(page: Page) -> None:
    """Helper to authenticate as admin and navigate to /admin/overview."""
    page.goto(f"{BASE_URL}/admin/overview", wait_until="domcontentloaded")
    
    # Check if redirected to login page
    if "/login" in page.url or page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]").is_visible():
        print("[AUTH] Performing admin login...")
        email_input = page.locator("input[type='email'], input[name='email'], input[placeholder*='email' i]").first
        pass_input = page.locator("input[type='password'], input[name='password']").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Login'), button:has-text('Sign In')").first
        
        email_input.fill(ADMIN_USER)
        pass_input.fill(ADMIN_PASS)
        submit_btn.click()
        
        page.wait_for_url("**/admin/**", timeout=15000)
        page.wait_for_load_state("networkidle")
        print("[AUTH] Logged in successfully.")


def test_sidebar_nav_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Sidebar Navigation and Section Switching
    Scenario ID: 031ee759-6bc3-4518-8d5c-31d8001cf9bc
    Subtest: Initial Navigation & Celebrities View Render
    Category: happy_path
    """
    screenshot_path = "reports/screenshots/031ee759_subtest_01.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    
    try:
        print("[STEP 1] Navigate to admin portal and authenticate")
        perform_login_if_needed(page)
        expect(page).to_have_url(f"{BASE_URL}/admin/overview")

        print("[STEP 2] Locate Celebrities sidebar link and click")
        celebrities_link = page.locator("a[href='/admin/celebrities'], nav a:has-text('Celebrities')").first
        expect(celebrities_link).to_be_visible()
        celebrities_link.click()

        print("[STEP 3] Verify Celebrities view renders properly")
        page.wait_for_url("**/admin/celebrities", timeout=10000)
        expect(page).to_have_url(f"{BASE_URL}/admin/celebrities")
        
        # Verify header or content for Celebrities
        heading = page.locator("h1, h2, h3, header, .page-header").filter(has_text="Celebrit").first
        expect(heading).to_be_visible()
        print("[PASS] Celebrities section loaded successfully.")

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAIL] Error in test_sidebar_nav_01_navigate_and_view: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_sidebar_nav_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Sidebar Navigation and Section Switching
    Scenario ID: 031ee759-6bc3-4518-8d5c-31d8001cf9bc
    Subtest: Interaction & Switching to Fans and Products Modules
    Category: happy_path
    """
    screenshot_path = "reports/screenshots/031ee759_subtest_02.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    
    try:
        print("[STEP 1] Authenticate and verify starting on admin route")
        perform_login_if_needed(page)

        print("[STEP 2] Click on Fans sidebar link")
        fans_link = page.locator("a[href='/admin/fans'], nav a:has-text('Fans')").first
        expect(fans_link).to_be_visible()
        fans_link.click()

        print("[STEP 3] Verify Fans Management page loads")
        page.wait_for_url("**/admin/fans", timeout=10000)
        expect(page).to_have_url(f"{BASE_URL}/admin/fans")
        fans_heading = page.locator("h1, h2, h3, header, .page-header").filter(has_text="Fan").first
        expect(fans_heading).to_be_visible()

        print("[STEP 4] Click on Products sidebar link")
        products_link = page.locator("a[href='/admin/products'], nav a:has-text('Products')").first
        expect(products_link).to_be_visible()
        products_link.click()

        print("[STEP 5] Verify Product Catalog page loads")
        page.wait_for_url("**/admin/products", timeout=10000)
        expect(page).to_have_url(f"{BASE_URL}/admin/products")
        products_heading = page.locator("h1, h2, h3, header, .page-header").filter(has_text="Product").first
        expect(products_heading).to_be_visible()
        print("[PASS] Fans and Products navigation completed successfully.")

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAIL] Error in test_sidebar_nav_02_interaction_and_validation: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_sidebar_nav_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Sidebar Navigation and Section Switching
    Scenario ID: 031ee759-6bc3-4518-8d5c-31d8001cf9bc
    Subtest: Verification Status Module and Navigation Loop Closure
    Category: happy_path
    """
    screenshot_path = "reports/screenshots/031ee759_subtest_03.png"
    os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
    
    try:
        print("[STEP 1] Authenticate and navigate to portal")
        perform_login_if_needed(page)

        print("[STEP 2] Click on Verification Status sidebar link")
        status_link = page.locator("a[href='/admin/verification-status'], nav a:has-text('Verification Status'), nav a:has-text('Status')").first
        expect(status_link).to_be_visible()
        status_link.click()

        print("[STEP 3] Verify Verification Status view and status tabs render")
        page.wait_for_url("**/admin/verification-status", timeout=10000)
        expect(page).to_have_url(f"{BASE_URL}/admin/verification-status")
        
        # Check presence of filter tabs or status elements
        status_container = page.locator("[role='tablist'], .tabs, table, .status-container, h1, h2, h3").first
        expect(status_container).to_be_visible()

        print("[STEP 4] Navigate back to Overview to verify return route")
        overview_link = page.locator("a[href='/admin/overview'], nav a:has-text('Overview')").first
        expect(overview_link).to_be_visible()
        overview_link.click()

        page.wait_for_url("**/admin/overview", timeout=10000)
        expect(page).to_have_url(f"{BASE_URL}/admin/overview")
        print("[PASS] Full navigation loop and Verification Status verified successfully.")

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAIL] Error in test_sidebar_nav_03_action_and_outcome: {e}. Screenshot captured at {screenshot_path}")
        raise

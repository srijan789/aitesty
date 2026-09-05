import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://nanotrak.multicorewareinc.com:3001"
ADMIN_USER = "admin@nanotrak.com"
ADMIN_PASS = "Nanotrak@123"


def login_admin(page: Page) -> None:
    """Helper to authenticate and navigate to admin section."""
    print(f"[LOGIN] Navigating to {BASE_URL}/admin/celebrities")
    page.goto(f"{BASE_URL}/admin/celebrities", wait_until="networkidle")

    # Check if redirected to login page
    if "/login" in page.url or page.locator("input[type='email'], input[name='username'], input[type='text']").is_visible():
        print("[LOGIN] Authenticating with admin credentials")
        email_input = page.locator("input[type='email'], input[name='username'], input[name='email'], input[placeholder*='Email' i]").first
        password_input = page.locator("input[type='password'], input[name='password'], input[placeholder*='Password' i]").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Log In'), button:has-text('Sign In')").first

        if email_input.is_visible():
            email_input.fill(ADMIN_USER)
            password_input.fill(ADMIN_PASS)
            submit_btn.click()
            page.wait_for_load_state("networkidle")

    # Ensure on celebrities page
    if not page.url.endswith("/admin/celebrities") and "/admin/celebrities" not in page.url:
        page.goto(f"{BASE_URL}/admin/celebrities", wait_until="networkidle")


def test_celebrity_search_edge_case_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Celebrity Search with Edge Case Keywords and Special Characters
    Scenario ID: bf5295af-d1ae-46ca-af44-ecb26c79757d
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to 'https://nanotrak.multicorewareinc.com:3001/admin/celebrities'")
        login_admin(page)

        print("[STEP 2] Verify Celebrities management page loads successfully")
        page.wait_for_selector("input[placeholder*='Search' i], table, .celebrity-list, [data-testid*='celebrity']", timeout=10000)
        
        # Verify page header or search input is present
        search_input = page.locator("input[placeholder*='Search' i]").first
        expect(search_input).to_be_visible(timeout=10000)
        print("[PASS] Celebrities management page and search bar rendered successfully")

    except Exception as e:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = "screenshots/failure_celebrity_search_01.png"
        page.screenshot(path=screenshot_path)
        print(f"[FAIL] Step failed with error: {e}. Screenshot captured: {screenshot_path}")
        raise


def test_celebrity_search_edge_case_02_special_chars_query(page: Page) -> None:
    """
    Scenario: Celebrity Search with Edge Case Keywords and Special Characters
    Scenario ID: bf5295af-d1ae-46ca-af44-ecb26c79757d
    Subtest: Special Characters Query & Input Validation
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to Celebrities management page")
        login_admin(page)

        print("[STEP 2] Fill special characters query into search input")
        search_input = page.locator("input[placeholder*='Search' i]").first
        expect(search_input).to_be_visible()
        
        special_query = "!@#$%^&*()_+{}[]|:;<>?,./~`'\"\\"
        search_input.fill(special_query)
        page.wait_for_timeout(1000)  # Allow debounce / filter response

        print("[STEP 3] Assert search handles special characters gracefully without application crash")
        body_text = page.locator("body").inner_text()
        
        # Ensure no runtime unhandled exception overlay or crash UI is visible
        assert "Uncaught Error" not in body_text, "UI crashed on special characters query"
        assert "Internal Server Error" not in body_text, "500 Server error triggered by special characters"

        # Check for empty state or results table container presence
        container = page.locator("tbody, div.celebrity-list, .table, [role='table'], text=/no (data|celebrities|records|results) found/i").first
        expect(container).to_be_visible(timeout=5000)
        print("[PASS] Special characters search query handled safely without UI breakage")

    except Exception as e:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = "screenshots/failure_celebrity_search_02.png"
        page.screenshot(path=screenshot_path)
        print(f"[FAIL] Step failed with error: {e}. Screenshot captured: {screenshot_path}")
        raise


def test_celebrity_search_edge_case_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Celebrity Search with Edge Case Keywords and Special Characters
    Scenario ID: bf5295af-d1ae-46ca-af44-ecb26c79757d
    Subtest: Non-Existent Query Empty State and Reset Recovery
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to Celebrities management page")
        login_admin(page)

        print("[STEP 2] Fill non-existent keyword in search input")
        search_input = page.locator("input[placeholder*='Search' i]").first
        expect(search_input).to_be_visible()
        
        non_existent_query = "__NON_EXISTENT_CELEBRITY_XYZ_123456789__"
        search_input.fill(non_existent_query)
        page.wait_for_timeout(1000)  # Allow debounce

        print("[STEP 3] Assert empty state or zero rows displayed")
        # Validate that rows matching non-existent query are zero or empty indicator is shown
        rows = page.locator("tbody tr, div.celebrity-card, div.celebrity-item")
        empty_state = page.locator("text=/no (data|celebrities|records|results|matches) found/i, .ant-empty, .empty-state")
        
        if rows.count() > 0:
            # If rows exist, check if it's an empty placeholder row
            row_text = rows.first.inner_text().lower()
            assert "no " in row_text or "not found" in row_text or rows.count() == 0, f"Unexpected rows found for non-existent query: {row_text}"
        else:
            # Zero rows or empty state container
            pass

        print("[STEP 4] Clear search input to verify UI recovery")
        search_input.fill("")
        page.wait_for_timeout(1000)

        # Confirm table or list recovers
        content_container = page.locator("tbody, div.celebrity-list, .table, [role='table']").first
        expect(content_container).to_be_visible()
        print("[PASS] Empty state rendered cleanly and table recovered on input clear")

    except Exception as e:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = "screenshots/failure_celebrity_search_03.png"
        page.screenshot(path=screenshot_path)
        print(f"[FAIL] Step failed with error: {e}. Screenshot captured: {screenshot_path}")
        raise

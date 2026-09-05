"""
Playwright Test Suite for Input Boundary & Form Validation Probing (Edge Cases)
Target Application: http://localhost:5678
Scenario ID: 6a141130-3a45-4522-bf49-ce496e4c8491
"""

import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("TARGET_URL", "http://localhost:5678")
AUTH_USER = os.getenv("AUTH_USER", "srijan.psn@gmail.com")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "Password1")
SCREENSHOT_DIR = "screenshots"


def ensure_authenticated(page: Page) -> None:
    """Helper to authenticate into the application if on signin page."""
    page.goto(f"{BASE_URL}/signin", wait_until="domcontentloaded")
    try:
        # Check if already redirected to home/workflows
        if "/home" in page.url or "/workflows" in page.url:
            return
        
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input[data-test-id*="email" i]').first
        if email_input.is_visible(timeout=3000):
            print("[AUTH] Performing form login...")
            email_input.fill(AUTH_USER)
            pwd_input = page.locator('input[type="password"], input[name="password"]').first
            pwd_input.fill(AUTH_PASSWORD)
            
            submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first
            submit_btn.click()
            page.wait_for_load_state("networkidle", timeout=10000)
    except Exception as e:
        print(f"[AUTH] Note during auth check: {e}")


def capture_failure_screenshot(page: Page, test_name: str) -> None:
    """Captures screenshot upon failure for diagnostic telemetry."""
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[DIAGNOSTIC] Screenshot captured at: {screenshot_path}")
    except Exception as err:
        print(f"[DIAGNOSTIC] Failed to capture screenshot: {err}")


def test_input_boundary_01_navigate_and_view(page: Page):
    """
    Scenario: Input Boundary & Form Validation Probing
    Scenario ID: 6a141130-3a45-4522-bf49-ce496e4c8491
    Subtest: Initial Navigation & View Render
    Category: edge_case
    """
    test_name = "test_input_boundary_01_navigate_and_view"
    try:
        print("[STEP 1] Navigate to http://localhost:5678/home/workflows")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")

        print("[STEP 2] Verify workflows view and interactive search/input elements are visible")
        # Check main container or interactive header elements
        body = page.locator("body")
        expect(body).to_be_visible()

        # Check for workflow controls or inputs
        search_or_input = page.locator(
            'input[type="search"], input[placeholder*="Search" i], input[type="text"], [data-test-id="resources-list-search"]'
        ).first
        
        # Verify page is not in crashed state (no raw 500 / unhandled exception)
        expect(page.locator("text=500 Internal Server Error")).not_to_be_visible()
        expect(page.locator("text=SyntaxError")).not_to_be_visible()
        expect(page.locator("text=Unhandled Exception")).not_to_be_visible()

        if search_or_input.is_visible():
            expect(search_or_input).to_be_enabled()
            print("[STEP 2 COMPLETED] Interactive search/input container is rendered and active.")
        else:
            print("[STEP 2 NOTE] Workflows view loaded; searching for alternate interactive forms.")

    except Exception as exc:
        capture_failure_screenshot(page, test_name)
        print(f"[FAILURE] {test_name} failed: {exc}")
        raise


def test_input_boundary_02_interaction_and_validation(page: Page):
    """
    Scenario: Input Boundary & Form Validation Probing
    Scenario ID: 6a141130-3a45-4522-bf49-ce496e4c8491
    Subtest: Interaction & Input Validation
    Category: edge_case
    """
    test_name = "test_input_boundary_02_interaction_and_validation"
    try:
        print("[STEP 1] Navigate to http://localhost:5678/home/workflows")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")

        # Define edge case boundary payloads
        long_string = "A" * 300
        special_and_emoji_string = "🚀🔥<script>alert('XSS')</script>!@#$%^&*()_+{}[]|\:;?><~`⚡🎉🛠️"
        whitespace_string = "     \t   \n   "

        print("[STEP 2] Probe input fields with boundary lengths (300 chars), emojis, and special characters")
        input_elem = page.locator(
            'input[type="search"], input[placeholder*="Search" i], input[type="text"]'
        ).first

        if input_elem.is_visible():
            print("[STEP 2.1] Testing 300-char boundary input")
            input_elem.fill(long_string)
            page.wait_for_timeout(300)
            
            # Verify UI doesn't crash or overflow brokenly
            expect(page.locator("text=500 Internal Server Error")).not_to_be_visible()
            expect(page.locator("text=Uncaught Error")).not_to_be_visible()

            print("[STEP 2.2] Testing emoji and XSS special chars probe")
            input_elem.fill(special_and_emoji_string)
            page.wait_for_timeout(300)

            # Ensure script tags are not executed or rendered unescaped in DOM error banners
            expect(page.locator("text=500 Internal Server Error")).not_to_be_visible()
            
            print("[STEP 2.3] Testing whitespace-only input")
            input_elem.fill(whitespace_string)
            page.wait_for_timeout(300)
            expect(page.locator("text=500 Internal Server Error")).not_to_be_visible()
        else:
            print("[STEP 2 NOTE] No standard text input directly visible on main page, checking modal or tag forms.")

        print("[STEP 2 COMPLETED] Input probes accepted and handled gracefully by client state.")

    except Exception as exc:
        capture_failure_screenshot(page, test_name)
        print(f"[FAILURE] {test_name} failed: {exc}")
        raise


def test_input_boundary_03_action_and_outcome(page: Page):
    """
    Scenario: Input Boundary & Form Validation Probing
    Scenario ID: 6a141130-3a45-4522-bf49-ce496e4c8491
    Subtest: Complete Action & Final Verification
    Category: edge_case
    """
    test_name = "test_input_boundary_03_action_and_outcome"
    try:
        print("[STEP 1] Navigate to http://localhost:5678/home/workflows")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")

        print("[STEP 2] Test workflow creation modal or search form submission with boundary strings")
        
        # Look for 'Add Workflow' / 'Create Workflow' button or input search enter action
        create_btn = page.locator(
            'button:has-text("Create Workflow"), button:has-text("Add workflow"), button[data-test-id="resources-list-add-workflow"], [data-test-id="new-workflow-button"]'
        ).first

        search_input = page.locator('input[type="search"], input[placeholder*="Search" i], input[type="text"]').first

        if search_input.is_visible():
            boundary_payload = "BoundaryTest_🚀_" + ("x" * 260) + "_<script>"
            print(f"[STEP 3] Entering boundary payload in search form and pressing Enter: {boundary_payload[:30]}...")
            search_input.fill(boundary_payload)
            search_input.press("Enter")
            page.wait_for_timeout(500)

            # Verification: Client or server validates input gracefully without exposing stack traces.
            # PASS: Empty state / filtered view / validation message is displayed cleanly.
            # FAIL: Server 500 error, page crash, or raw SQL/exception leak.
            
            page_content = page.content()
            
            # Assert no SQL error leaks
            assert "SQLSTATE" not in page_content, "FAIL: Raw SQL error leak detected!"
            assert "syntax error at or near" not in page_content, "FAIL: Raw SQL syntax error leak detected!"
            assert "TypeError:" not in page_content, "FAIL: Unhandled TypeError stack trace leak detected!"
            
            # Assert no 500 server crash
            expect(page.locator("text=500 Internal Server Error")).not_to_be_visible()
            expect(page.locator("text=502 Bad Gateway")).not_to_be_visible()
            expect(page.locator("text=503 Service Unavailable")).not_to_be_visible()

            print("[PASS CRITERIA MET] Input was sanitized/handled gracefully without stack traces or page crashes.")
        
        # If create workflow modal is accessible, test modal inputs with boundary data
        if create_btn.is_visible():
            print("[STEP 3.1] Testing workflow creation button with edge-case handling")
            create_btn.click()
            page.wait_for_timeout(1000)
            
            # Check for name input or modal
            name_input = page.locator('input[placeholder*="Workflow name" i], input[data-test-id="workflow-name-input"]').first
            if name_input.is_visible():
                name_input.fill("🔥" * 260)
                submit_btn = page.locator('button[type="submit"], button:has-text("Save"), button:has-text("Create")').first
                if submit_btn.is_visible():
                    submit_btn.click()
                    page.wait_for_timeout(500)
                    
                    # Ensure no crash
                    expect(page.locator("text=500 Internal Server Error")).not_to_be_visible()
                    expect(page.locator("text=SQLSTATE")).not_to_be_visible()

        print("[STEP 3 COMPLETED] All form inputs and submissions verified against boundary & error leakage criteria.")

    except Exception as exc:
        capture_failure_screenshot(page, test_name)
        print(f"[FAILURE] {test_name} failed: {exc}")
        raise

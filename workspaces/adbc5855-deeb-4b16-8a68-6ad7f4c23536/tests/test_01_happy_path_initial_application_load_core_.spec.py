import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("BASE_URL", "http://localhost:5678")
AUTH_USER = os.getenv("AUTH_USER", "srijan.psn@gmail.com")
AUTH_PASS = os.getenv("AUTH_PASS", "Password1")


def login_if_needed(page: Page) -> None:
    """Helper to authenticate if the app redirects to the sign-in / login page."""
    # Check if redirected to signin/login or if login inputs are present
    if "/signin" in page.url or "/login" in page.url or page.locator('input[type="email"], input[name="email"], input[name="username"]').is_visible():
        print("[AUTH] Sign-in required. Performing login...")
        email_input = page.locator('input[type="email"], input[name="email"], input[name="username"]').first
        email_input.fill(AUTH_USER)
        password_input = page.locator('input[type="password"], input[name="password"]').first
        password_input.fill(AUTH_PASS)
        submit_btn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').first
        submit_btn.click()
        page.wait_for_load_state("networkidle")


def test_workflow_initial_load_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Initial Application Load & Core View Render (Workflows - n8n)
    Scenario ID: 912b5b07-b5ae-4ee3-85aa-3f5e5dc1cf33
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    try:
        print("[STEP 1] Navigate to target URL 'http://localhost:5678/home/workflows'")
        response = page.goto(f"{BASE_URL}/home/workflows", wait_until="domcontentloaded", timeout=15000)
        
        assert response is not None, "Failed to get a response from server"
        print(f"[STEP 1 DIAGNOSTIC] HTTP Status: {response.status}")
        assert response.status in [200, 304], f"Expected HTTP 200/304, got {response.status}"

        # Handle login if redirected to signin
        login_if_needed(page)

        print("[STEP 2] Assert DOM ready and body rendered")
        expect(page.locator("body")).to_be_visible(timeout=10000)

    except Exception as exc:
        os.makedirs("test-results/screenshots", exist_ok=True)
        screenshot_path = "test-results/screenshots/912b5b07_01_navigate_failed.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot captured at {screenshot_path}")
        print(f"[FAILURE DETAILS] {exc}")
        raise


def test_workflow_initial_load_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Initial Application Load & Core View Render (Workflows - n8n)
    Scenario ID: 912b5b07-b5ae-4ee3-85aa-3f5e5dc1cf33
    Subtest: Interaction & Primary Navigation Validation
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate and verify active session")
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle", timeout=15000)
        login_if_needed(page)

        print("[STEP 2] Assert primary navigation bar and header elements are rendered")
        nav_locator = page.locator("nav, aside, header, [data-test-id='navigation-menu'], [class*='sidebar']").first
        expect(nav_locator).to_be_visible(timeout=10000)

        print("[STEP 3] Verify page title / heading contains application context")
        expect(page).to_have_title(lambda title: "n8n" in title or "Workflows" in title, timeout=5000)

    except Exception as exc:
        os.makedirs("test-results/screenshots", exist_ok=True)
        screenshot_path = "test-results/screenshots/912b5b07_02_validation_failed.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot captured at {screenshot_path}")
        print(f"[FAILURE DETAILS] {exc}")
        raise


def test_workflow_initial_load_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Initial Application Load & Core View Render (Workflows - n8n)
    Scenario ID: 912b5b07-b5ae-4ee3-85aa-3f5e5dc1cf33
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to Workflows view")
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle", timeout=15000)
        login_if_needed(page)

        print("[STEP 2] Assert core landing elements and main content are visible without crash")
        # Assert main content container or workflows area
        main_content = page.locator("main, #app, [class*='workflows'], [data-test-id='resources-list']").first
        expect(main_content).to_be_visible(timeout=10000)

        # Check for workflow action button (e.g. 'Add workflow' or 'Create workflow' or workflow card list)
        action_button = page.locator("button:has-text('Add workflow'), button:has-text('Create workflow'), button:has-text('Add from template'), [data-test-id='create-workflow-button']").first
        expect(action_button).to_be_visible(timeout=10000)

        print("[STEP 3] Final check: Verify page URL is on workflows path")
        assert "/workflows" in page.url or "/home" in page.url, f"Unexpected page URL: {page.url}"
        print(f"[SUCCESS] Core view rendered successfully at {page.url}")

    except Exception as exc:
        os.makedirs("test-results/screenshots", exist_ok=True)
        screenshot_path = "test-results/screenshots/912b5b07_03_outcome_failed.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot captured at {screenshot_path}")
        print(f"[FAILURE DETAILS] {exc}")
        raise

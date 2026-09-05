import pytest
import os
from playwright.sync_api import Page, expect, Response

BASE_URL = "http://localhost:5678"
AUTH_CREDENTIALS = {
    "username": "srijan.psn@gmail.com",
    "password": "Password1"
}

def ensure_authenticated(page: Page) -> None:
    """Helper to authenticate user into n8n if redirected to signin."""
    print("[AUTH] Checking authentication state...")
    page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")
    
    # If redirected to signin page, perform form authentication
    if "/signin" in page.url or page.locator("input[name='email'], input[type='email']").is_visible():
        print(f"[AUTH] Redirected to signin. Authenticating as {AUTH_CREDENTIALS['username']}...")
        email_input = page.locator("input[name='email'], input[type='email']")
        password_input = page.locator("input[name='password'], input[type='password']")
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')")

        email_input.fill(AUTH_CREDENTIALS["username"])
        password_input.fill(AUTH_CREDENTIALS["password"])
        submit_btn.click()
        page.wait_for_load_state("networkidle")
        print("[AUTH] Authentication form submitted.")


def test_workflows_view_01_navigate_and_view(page: Page):
    """
    Scenario: Initial Application Load & Core View Render (Workflows - n8n)
    Scenario ID: 1d62d62b-a86e-453c-9768-6ea15d3f7a0e
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    try:
        print("[STEP 1] Navigate to http://localhost:5678/home/workflows and verify HTTP 200 response")
        ensure_authenticated(page)
        
        response = page.goto(f"{BASE_URL}/home/workflows", wait_until="domcontentloaded")
        assert response is not None, "Failed to get response from server"
        assert response.status == 200 or response.status == 304, f"Expected HTTP 200/304, got {response.status}"
        print(f"[STEP 1 SUCCESS] Navigated to {page.url} with HTTP status {response.status}")

        print("[STEP 2] Assert page title and DOM readiness")
        expect(page).to_have_title("Workflows - n8n", timeout=10000)
        print("[STEP 2 SUCCESS] Page title matches 'Workflows - n8n'")

    except Exception as exc:
        screenshot_path = "failure_1d62d62b_01_nav.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot captured at: {screenshot_path}")
        print(f"[FAILURE DETAILS] {str(exc)}")
        raise


def test_workflows_view_02_interaction_and_validation(page: Page):
    """
    Scenario: Initial Application Load & Core View Render (Workflows - n8n)
    Scenario ID: 1d62d62b-a86e-453c-9768-6ea15d3f7a0e
    Subtest: Navigation Elements & Console Error Validation
    Category: happy_path
    """
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    try:
        print("[STEP 1] Navigate to workflows page and verify primary layout")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")

        print("[STEP 2] Assert primary navigation bar and layout components exist")
        # Check sidebar/navigation or header components
        nav_locator = page.locator("nav, aside, header, [data-test-id='sidebar'], [data-test-id='main-sidebar']")
        expect(nav_locator.first).to_be_visible(timeout=8000)
        print("[STEP 2 SUCCESS] Navigation element is rendered and visible")

        print("[STEP 3] Check for zero uncaught JavaScript console errors")
        critical_errors = [err for err in console_errors if not any(ign in err for ign in ["favicon", "ResizeObserver"])]
        assert len(critical_errors) == 0, f"Uncaught JS console errors detected: {critical_errors}"
        print("[STEP 3 SUCCESS] No uncaught critical JS errors detected")

    except Exception as exc:
        screenshot_path = "failure_1d62d62b_02_validation.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot captured at: {screenshot_path}")
        print(f"[FAILURE DETAILS] {str(exc)}")
        raise


def test_workflows_view_03_action_and_outcome(page: Page):
    """
    Scenario: Initial Application Load & Core View Render (Workflows - n8n)
    Scenario ID: 1d62d62b-a86e-453c-9768-6ea15d3f7a0e
    Subtest: Main View Components & Action Controls Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to workflows page")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")

        print("[STEP 2] Verify primary workflow view action triggers")
        # Ensure main content area or workflow creation button/empty state is displayed
        main_content = page.locator("main, #app, [role='main'], div[class*='workflow']")
        expect(main_content.first).to_be_visible(timeout=8000)

        # Verify presence of create/add workflow button or workflows header
        action_button = page.locator(
            "button:has-text('Create workflow'), button:has-text('Add workflow'), button:has-text('New workflow'), [data-test-id='workflow-add-button']"
        ).first
        expect(action_button).to_be_visible(timeout=8000)
        print("[STEP 2 SUCCESS] Primary workflow action controls are interactable and visible")

        print("[STEP 3] Confirm page is fully interactive and body is visible")
        expect(page.locator("body")).to_be_visible()
        print("[STEP 3 SUCCESS] Workflow landing components fully rendered and ready")

    except Exception as exc:
        screenshot_path = "failure_1d62d62b_03_outcome.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Diagnostic screenshot captured at: {screenshot_path}")
        print(f"[FAILURE DETAILS] {str(exc)}")
        raise

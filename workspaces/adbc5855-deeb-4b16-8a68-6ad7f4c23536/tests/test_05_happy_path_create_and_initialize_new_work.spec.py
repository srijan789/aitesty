import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
USER_EMAIL = os.getenv("N8N_EMAIL", "srijan.psn@gmail.com")
USER_PASSWORD = os.getenv("N8N_PASSWORD", "Password1")


@pytest.fixture(autouse=True)
def ensure_authenticated(page: Page):
    """Authenticate to n8n if not already authenticated."""
    print(f"[AUTH] Navigating to login/home at {BASE_URL}")
    page.goto(f"{BASE_URL}/signin")
    page.wait_for_load_state("domcontentloaded")

    # Check if login form is displayed
    email_input = page.locator('input[name="email"], input[type="email"], input[name="username"]')
    password_input = page.locator('input[name="password"], input[type="password"]')

    if email_input.is_visible(timeout=3000):
        print(f"[AUTH] Filling credentials for {USER_EMAIL}")
        email_input.fill(USER_EMAIL)
        password_input.fill(USER_PASSWORD)
        page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in")').click()
        page.wait_for_load_state("networkidle")
        print("[AUTH] Successfully submitted login form.")
    else:
        print("[AUTH] Already authenticated or redirected.")


def test_create_workflow_01_navigate_and_view(page: Page):
    """
    Scenario: Create and Initialize New Workflow Canvas
    Scenario ID: 7ab4a577-30c9-4590-9dbe-af2abb03fad6
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigating to workflow creation endpoint: /workflow/new")
        page.goto(f"{BASE_URL}/workflow/new")
        page.wait_for_load_state("domcontentloaded")

        print("[STEP 2] Verifying workflow canvas and editor container view render")
        canvas_or_editor = page.locator('.vue-flow, [data-test-id="canvas"], .canvas-container, .workflow-canvas, [class*="canvas"]')
        expect(canvas_or_editor.first).to_be_visible(timeout=10000)
        print("[STEP 2] Workflow canvas is visible.")

    except Exception as e:
        screenshot_path = "failure_01_navigate_and_view.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Screenshot saved to {screenshot_path}. Error: {e}")
        raise


def test_create_workflow_02_interaction_and_validation(page: Page):
    """
    Scenario: Create and Initialize New Workflow Canvas
    Scenario ID: 7ab4a577-30c9-4590-9dbe-af2abb03fad6
    Subtest: Interaction & Input Validation
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigating to /workflow/new to validate canvas controls")
        page.goto(f"{BASE_URL}/workflow/new")
        page.wait_for_load_state("networkidle")

        print("[STEP 2] Validating Editor and Executions navigation/tabs")
        editor_tab = page.locator('button:has-text("Editor"), [data-test-id="workflow-editor-tab"], div[role="tab"]:has-text("Editor")')
        executions_tab = page.locator('button:has-text("Executions"), [data-test-id="workflow-executions-tab"], div[role="tab"]:has-text("Executions")')
        
        expect(editor_tab.first).to_be_visible(timeout=5000)
        print("[STEP 2] Editor tab is confirmed visible.")
        expect(executions_tab.first).to_be_visible(timeout=5000)
        print("[STEP 2] Executions tab is confirmed visible.")

        print("[STEP 3] Validating trigger node / initial prompt or add node action")
        add_node_btn = page.locator('button:has-text("Add first step"), [data-test-id="canvas-add-node-button"], button:has-text("Add node"), [class*="add-node"], [class*="node-creator"]')
        expect(add_node_btn.first).to_be_visible(timeout=5000)
        print("[STEP 3] Initial node prompt / add node button verified.")

    except Exception as e:
        screenshot_path = "failure_02_interaction_and_validation.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Screenshot saved to {screenshot_path}. Error: {e}")
        raise


def test_create_workflow_03_action_and_outcome(page: Page):
    """
    Scenario: Create and Initialize New Workflow Canvas
    Scenario ID: 7ab4a577-30c9-4590-9dbe-af2abb03fad6
    Subtest: Complete Action & Final Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigating to /workflow/new for complete action verification")
        page.goto(f"{BASE_URL}/workflow/new")
        page.wait_for_load_state("networkidle")

        print("[STEP 2] Asserting Publish button and Workflow controls presence")
        publish_button = page.locator('button:has-text("Publish"), [data-test-id="workflow-publish-button"], button:has-text("Save")')
        expect(publish_button.first).to_be_visible(timeout=10000)
        print("[STEP 2] Publish/Save action control confirmed visible.")

        print("[STEP 3] Verifying URL pattern matches workflow structure")
        expect(page).to_have_url(f"{BASE_URL}/workflow/")
        current_url = page.url
        print(f"[STEP 3] Current workflow URL verified: {current_url}")

    except Exception as e:
        screenshot_path = "failure_03_action_and_outcome.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Screenshot saved to {screenshot_path}. Error: {e}")
        raise

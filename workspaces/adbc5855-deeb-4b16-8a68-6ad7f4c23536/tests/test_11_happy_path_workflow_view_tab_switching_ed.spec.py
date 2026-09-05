import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.getenv("TARGET_URL", "http://localhost:5678")
AUTH_USER = os.getenv("AUTH_USERNAME", "srijan.psn@gmail.com")
AUTH_PASS = os.getenv("AUTH_PASSWORD", "Password1")


def ensure_authenticated(page: Page) -> None:
    """Helper to ensure user is logged in to n8n instance."""
    page.goto(f"{BASE_URL}/workflow/new", wait_until="domcontentloaded")
    
    # Check if redirected to signin page
    if "/signin" in page.url or page.locator("input[name='emailOrUsername'], input[type='email']").is_visible():
        email_input = page.locator("input[name='emailOrUsername'], input[type='email'], input[name='email']").first
        password_input = page.locator("input[type='password'], input[name='password']").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first
        
        email_input.fill(AUTH_USER)
        password_input.fill(AUTH_PASS)
        submit_btn.click()
        
        page.wait_for_url("**/workflow/**", timeout=15000)
    
    page.wait_for_load_state("networkidle")


def test_workflow_view_tab_switching_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Workflow View Tab Switching (Editor vs Executions)
    Scenario ID: d47bede2-4043-45dc-9d92-00527d1a21a6
    Subtest: Initial Navigation & View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to workflow view and ensure authentication")
        ensure_authenticated(page)
        
        print("[STEP 2] Verify workflow canvas and editor navigation tabs are visible")
        page.goto(f"{BASE_URL}/workflow/new", wait_until="networkidle")
        
        editor_tab = page.locator("button:has-text('Editor'), [data-test-id='workflow-navigation-editor-tab'], a:has-text('Editor')").first
        executions_tab = page.locator("button:has-text('Executions'), [data-test-id='workflow-navigation-executions-tab'], a:has-text('Executions')").first
        
        expect(editor_tab).to_be_visible(timeout=10000)
        expect(executions_tab).to_be_visible(timeout=10000)
        
        # Verify Editor canvas container or node add button is present
        canvas_or_add_node = page.locator(".canvas, [data-test-id='canvas'], button:has-text('Add first step'), .node-view").first
        expect(canvas_or_add_node).to_be_visible(timeout=10000)
        print("[STEP 3] Verified Editor canvas and tab bar loaded successfully")
        
    except Exception as e:
        screenshot_path = "screenshot_tab_switching_01_failure.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Initial navigation and view render failed: {e}. Screenshot captured to {screenshot_path}")
        raise


def test_workflow_view_tab_switching_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Workflow View Tab Switching (Editor vs Executions)
    Scenario ID: d47bede2-4043-45dc-9d92-00527d1a21a6
    Subtest: Interaction & Tab Switch to Executions
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to workflow view")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/workflow/new", wait_until="networkidle")
        
        print("[STEP 2] Click on Executions tab")
        executions_tab = page.locator("button:has-text('Executions'), [data-test-id='workflow-navigation-executions-tab'], a:has-text('Executions')").first
        expect(executions_tab).to_be_visible(timeout=10000)
        executions_tab.click()
        
        print("[STEP 3] Verify Executions view or empty state is displayed")
        executions_view = page.locator("[data-test-id='executions-view'], .executions-view, :text('No executions'), :text('Executions')").first
        expect(executions_view).to_be_visible(timeout=10000)
        print("[STEP 4] Verified Executions view rendered without UI error")
        
    except Exception as e:
        screenshot_path = "screenshot_tab_switching_02_failure.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Tab switch to Executions failed: {e}. Screenshot captured to {screenshot_path}")
        raise


def test_workflow_view_tab_switching_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Workflow View Tab Switching (Editor vs Executions)
    Scenario ID: d47bede2-4043-45dc-9d92-00527d1a21a6
    Subtest: Complete Action & Return to Editor Canvas
    Category: happy_path
    """
    try:
        print("[STEP 1] Navigate to workflow view")
        ensure_authenticated(page)
        page.goto(f"{BASE_URL}/workflow/new", wait_until="networkidle")
        
        print("[STEP 2] Switch to Executions tab")
        executions_tab = page.locator("button:has-text('Executions'), [data-test-id='workflow-navigation-executions-tab'], a:has-text('Executions')").first
        expect(executions_tab).to_be_visible(timeout=10000)
        executions_tab.click()
        
        print("[STEP 3] Switch back to Editor tab")
        editor_tab = page.locator("button:has-text('Editor'), [data-test-id='workflow-navigation-editor-tab'], a:has-text('Editor')").first
        expect(editor_tab).to_be_visible(timeout=10000)
        editor_tab.click()
        
        print("[STEP 4] Verify Editor canvas view is fully restored")
        canvas_or_add_node = page.locator(".canvas, [data-test-id='canvas'], button:has-text('Add first step'), .node-view").first
        expect(canvas_or_add_node).to_be_visible(timeout=10000)
        print("[STEP 5] Active view state seamlessly switched between Editor and Executions without error")
        
    except Exception as e:
        screenshot_path = "screenshot_tab_switching_03_failure.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Tab switch back to Editor failed: {e}. Screenshot captured to {screenshot_path}")
        raise

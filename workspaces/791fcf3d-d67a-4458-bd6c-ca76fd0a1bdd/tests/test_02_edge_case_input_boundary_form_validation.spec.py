import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("TARGET_URL", "http://localhost:5678")
USERNAME = os.environ.get("TARGET_USERNAME", "srijan.psn@gmail.com")
PASSWORD = os.environ.get("TARGET_PASSWORD", "Password1")


def authenticate_if_needed(page: Page) -> None:
    """Helper to log in to n8n if redirected to signin page."""
    page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")
    
    # Check if redirected to signin/login page
    if "/signin" in page.url or "/login" in page.url or page.locator("input[name='email'], input[type='email']").is_visible():
        print("[SETUP] Logging into application")
        email_input = page.locator("input[name='email'], input[type='email'], input[placeholder*='name@email.com'], input[name='value']").first
        password_input = page.locator("input[name='password'], input[type='password']").first
        
        email_input.fill(USERNAME)
        password_input.fill(PASSWORD)
        
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first
        submit_btn.click()
        page.wait_for_load_state("networkidle")


@pytest.fixture(autouse=True)
def setup_diagnostics(page: Page):
    """Setup network and console error diagnostics."""
    captured_errors = []
    page.on("console", lambda msg: captured_errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ["error", "warning"] else None)
    page.on("pageerror", lambda exc: captured_errors.append(f"PAGE_ERROR: {exc}"))
    page.on("response", lambda resp: captured_errors.append(f"HTTP_{resp.status}: {resp.url}") if resp.status >= 500 else None)
    
    yield captured_errors
    
    # Log any captured server/runtime errors after test
    if captured_errors:
        print("\n--- Diagnostic Log captured during execution ---")
        for err in captured_errors:
            print(f"  {err}")


def test_input_boundary_and_form_validation(page: Page, setup_diagnostics):
    """
    Scenario ID: 0021b73d-c0f2-41c1-aad5-e2b381799f33
    Title: Input Boundary & Form Validation Probing
    Description: Probe input fields with boundary lengths (255+ characters), emojis,
                 and whitespace-only submissions to ensure graceful validation without server 500 or stack traces.
    """
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    screenshot_path = os.path.join(screenshot_dir, "test_input_boundary_validation.png")

    try:
        # Step 1: Navigate to http://localhost:5678/home/workflows
        print("[STEP 1] Navigate to 'http://localhost:5678/home/workflows'")
        authenticate_if_needed(page)
        
        page.goto(f"{BASE_URL}/home/workflows", wait_until="networkidle")
        expect(page).to_have_url(lambda u: "/home/workflows" in u or "/workflows" in u or "/home" in u)
        
        # Test boundary strings
        long_string = "A" * 300
        special_char_emoji_string = "🔥🚀 <script>alert('test')</script> SELECT * FROM users; -- 💡🔧"
        whitespace_string = "     "

        # Locate interactive inputs on the page (e.g., search bar, workflow creation / filter)
        print("[STEP 2] Fill on 'input' with boundary length (300 chars), emojis, and special characters")
        
        # Try search input or create new workflow / tag / folder modal if available
        search_input = page.locator("input[type='search'], input[placeholder*='Search'], input[data-test-id='resources-list-search'], input.el-input__inner").first
        
        if search_input.is_visible():
            # Probe 1: Long boundary string in search
            print("[SUBSTEP 2.1] Testing 300+ character boundary string in search filter")
            search_input.fill(long_string)
            page.wait_for_timeout(500)
            
            # Check for crashes or stack traces
            body_text = page.locator("body").inner_text()
            assert "Internal Server Error" not in body_text, "Server 500 exposed on long input string"
            assert "TypeError:" not in body_text and "Traceback (most recent call last)" not in body_text, "Stack trace exposed on long input string"
            
            # Probe 2: Special chars and emojis
            print("[SUBSTEP 2.2] Testing emoji and XSS/SQL injection string")
            search_input.fill(special_char_emoji_string)
            page.wait_for_timeout(500)
            
            body_text = page.locator("body").inner_text()
            assert "Internal Server Error" not in body_text, "Server 500 exposed on special characters"
            assert "<script>alert" not in body_text, "Raw unescaped script tag rendered in page body"

            # Probe 3: Whitespace only
            print("[SUBSTEP 2.3] Testing whitespace-only input")
            search_input.fill(whitespace_string)
            page.wait_for_timeout(500)
            search_input.clear()

        # Step 3: Trigger interactive form modal if available (e.g. Add workflow / New Tag / Create Folder)
        print("[STEP 3] Probing form submission modal with boundary values")
        add_btn = page.locator("button:has-text('Add workflow'), button:has-text('Create workflow'), button:has-text('New'), [data-test-id='workflow-add-button']").first
        
        if add_btn.is_visible():
            add_btn.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

        # Look for any form or editable fields (like workflow name, tag input, etc.)
        name_input = page.locator("input[data-test-id='workflow-name-input'], input[placeholder*='Workflow name'], input.el-input__inner, input[type='text']").first
        if name_input.is_visible():
            print("[STEP 3.1] Testing form validation with long boundary value")
            name_input.fill(long_string)
            
            # Attempt submission if submit button exists
            submit_btn = page.locator("button[type='submit'], button:has-text('Save'), button:has-text('Create')").first
            if submit_btn.is_visible():
                print("[STEP 3.2] Click on 'button[type='submit']'")
                submit_btn.click()
                page.wait_for_timeout(1000)

        # Verify no 500 errors were captured in network responses
        server_errors = [err for err in setup_diagnostics if "HTTP_5" in err]
        assert len(server_errors) == 0, f"Server returned 500 errors during boundary tests: {server_errors}"

        # Verify no uncaught fatal exceptions or raw SQL leaks in the DOM
        page_content = page.content()
        assert "syntax error at or near" not in page_content.lower(), "Raw SQL syntax error exposed to client"
        assert "uncaught exception" not in page_content.lower(), "Uncaught exception string exposed in page content"

        print("[SUCCESS] Boundary length, emoji, and whitespace probing handled gracefully without crashes or stack traces.")

    except Exception as e:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed: {e}. Screenshot captured at '{screenshot_path}'")
        raise

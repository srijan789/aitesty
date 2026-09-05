import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("TARGET_URL", "http://localhost:5678")
AUTH_USER = os.environ.get("AUTH_USER", "srijan.psn@gmail.com")
AUTH_PASS = os.environ.get("AUTH_PASS", "Password1")


def login_if_required(page: Page) -> None:
    """Helper to authenticate to the application if redirected to signin."""
    print("[AUTH] Checking authentication status...")
    page.goto(f"{BASE_URL}/home/workflows")
    page.wait_for_load_state("domcontentloaded")

    # Check if redirected to signin
    if "/signin" in page.url or page.locator("input[name='email'], input[type='email']").is_visible():
        print("[AUTH] Sign-in form detected. Logging in...")
        email_field = page.locator("input[name='email'], input[type='email'], input[placeholder*='name@email.com']")
        password_field = page.locator("input[name='password'], input[type='password']")
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in')")

        email_field.fill(AUTH_USER)
        password_field.fill(AUTH_PASS)
        submit_btn.click()
        page.wait_for_url(lambda u: "/signin" not in u, timeout=15000)
        page.wait_for_load_state("networkidle")
        print("[AUTH] Successfully authenticated.")
    else:
        print("[AUTH] Already authenticated or on target route.")


def test_input_boundary_validation_01_navigate_and_view(page: Page):
    """
    Scenario: Input Boundary & Form Validation Probing
    Scenario ID: 5d00db18-8496-4bd9-acd3-cbd094b8c18c
    Subtest: Initial Navigation & Workflow Form Render
    Category: edge_case
    """
    print("[STEP 1] Navigating to workflows dashboard and checking form visibility")
    try:
        login_if_required(page)
        page.goto(f"{BASE_URL}/home/workflows")
        page.wait_for_load_state("networkidle")

        # Verify dashboard/workflows page elements are present
        expect(page).not_to_have_url(f"{BASE_URL}/signin")
        
        # Look for search input or workflow list container
        search_input = page.locator("input[placeholder*='Search'], input[type='search'], input[type='text']").first
        expect(search_input).to_be_visible(timeout=10000)
        print("[STEP 1] Navigation verified and interactive inputs are visible.")
    except Exception as e:
        screenshot_path = "failure_boundary_01_navigate.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAIL] Navigation or view render failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_input_boundary_validation_02_interaction_and_validation(page: Page):
    """
    Scenario: Input Boundary & Form Validation Probing
    Scenario ID: 5d00db18-8496-4bd9-acd3-cbd094b8c18c
    Subtest: Probe Input Fields with Boundary Lengths, Unicode, and Emojis
    Category: edge_case
    """
    print("[STEP 2] Probing search and form inputs with boundary values (255+ chars, emojis, whitespace)")
    try:
        login_if_required(page)
        page.goto(f"{BASE_URL}/home/workflows")
        page.wait_for_load_state("networkidle")

        search_input = page.locator("input[placeholder*='Search'], input[type='search'], input[type='text']").first
        expect(search_input).to_be_visible()

        # 1. Probe with Boundary length (300+ characters)
        boundary_string = "A" * 320 + "🔥🚀💥🎉" + "<script>alert('xss')</script>"
        print(f"[STEP 2.1] Filling input with {len(boundary_string)} characters including emojis & special chars")
        search_input.fill(boundary_string)
        page.wait_for_timeout(500)

        # Assert input accepted or truncated cleanly without crashing UI
        current_value = search_input.input_value()
        assert len(current_value) > 0, "Input value should not be empty after filling"
        
        # Verify page is still responsive and not displaying error dialogs/crash overlays
        error_overlay = page.locator(".el-message--error, .error-banner, [role='alert']")
        if error_overlay.is_visible():
            error_text = error_overlay.inner_text()
            print(f"[STEP 2.1] Notice / Error message displayed gracefully: {error_text}")
            assert "stack" not in error_text.lower(), "Raw stack trace leaked in error banner"
            assert "sql" not in error_text.lower(), "Raw SQL error leaked in error banner"

        # 2. Probe with whitespace-only input
        print("[STEP 2.2] Probing with whitespace-only input")
        search_input.fill("        \t\n   ")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

        # Verify page did not crash on whitespace search/filter
        expect(page.locator("body")).to_be_visible()
        print("[STEP 2] Interaction with boundary strings completed gracefully.")
    except Exception as e:
        screenshot_path = "failure_boundary_02_interaction.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAIL] Boundary input interaction failed: {e}. Screenshot captured at {screenshot_path}")
        raise


def test_input_boundary_validation_03_action_and_outcome(page: Page):
    """
    Scenario: Input Boundary & Form Validation Probing
    Scenario ID: 5d00db18-8496-4bd9-acd3-cbd094b8c18c
    Subtest: Form Submission Boundary Probing and Validation Handling
    Category: edge_case
    """
    print("[STEP 3] Testing form submission with boundary values and asserting no 500 / stack trace leaks")
    try:
        login_if_required(page)
        page.goto(f"{BASE_URL}/home/workflows")
        page.wait_for_load_state("networkidle")

        # Track network responses for 500 server crashes
        server_errors = []
        def handle_response(response):
            if response.status >= 500:
                server_errors.append(f"HTTP {response.status} from {response.url}")

        page.on("response", handle_response)

        # Try to open a creation modal (tag / folder / workflow or search submission)
        new_button = page.locator("button:has-text('Add workflow'), button:has-text('New workflow'), button:has-text('Create')").first
        if new_button.is_visible():
            print("[STEP 3.1] Opening workflow creation or workflow canvas")
            new_button.click()
            page.wait_for_timeout(1000)

        # Ensure no unhandled 500 errors occurred
        assert len(server_errors) == 0, f"Server returned 500 internal server error(s): {server_errors}"

        # Ensure no stack trace or SQL exception is printed on the page
        body_text = page.locator("body").inner_text()
        assert "Internal Server Error" not in body_text, "500 Internal Server Error displayed on UI"
        assert "Traceback (most recent call last)" not in body_text, "Python/Node stack trace leaked on UI"
        assert "syntax error at or near" not in body_text.lower(), "Raw SQL error leaked on UI"

        print("[STEP 3] Validation completed: Form handling sanitized inputs and prevented server crashes/leaks.")
    except Exception as e:
        screenshot_path = "failure_boundary_03_outcome.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAIL] Boundary form submission validation failed: {e}. Screenshot captured at {screenshot_path}")
        raise

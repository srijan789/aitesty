import pytest
from playwright.sync_api import Page, expect


def test_special_char_injection_login_01_navigate_and_view(page: Page):
    """
    Scenario: Special Character and Injection Resilience in Login Identifier
    Scenario ID: e4d08099-3f54-4238-9d56-abb53fa58c17
    Subtest: Initial Navigation & Sign-In Form View Render
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page http://localhost:5678/signin")
        page.goto("http://localhost:5678/signin", wait_until="networkidle")

        print("[STEP 2] Verify login form controls are rendered")
        login_input = page.locator("#emailOrLdapLoginId, input[name='emailOrLdapLoginId'], input[name='email']")
        expect(login_input.first).to_be_visible()

        password_input = page.locator("#password, input[name='password'], input[type='password']")
        expect(password_input.first).to_be_visible()

        signin_button = page.locator("button:has-text('Sign in'), button[type='submit']")
        expect(signin_button.first).to_be_visible()
        print("[STEP 3] Sign-in page rendered successfully with expected form elements")
    except Exception as e:
        page.screenshot(path="screenshot_edge_case_nav_fail.png", full_page=True)
        print(f"[ERROR] Navigation or view render failed: {e}")
        raise


def test_special_char_injection_login_02_interaction_and_validation(page: Page):
    """
    Scenario: Special Character and Injection Resilience in Login Identifier
    Scenario ID: e4d08099-3f54-4238-9d56-abb53fa58c17
    Subtest: Input Special Characters and Injection Payload
    Category: edge_case
    """
    try:
        print("[STEP 1] Navigate to signin page")
        page.goto("http://localhost:5678/signin", wait_until="networkidle")

        payload = "<script>alert('xss')</script>' OR '1'='1' --"
        print(f"[STEP 2] Fill login identifier with payload: {payload}")
        login_input = page.locator("#emailOrLdapLoginId, input[name='emailOrLdapLoginId'], input[name='email']").first
        login_input.fill(payload)

        print("[STEP 3] Fill password field")
        password_input = page.locator("#password, input[name='password'], input[type='password']").first
        password_input.fill("SamplePassword123!")

        print("[STEP 4] Verify login input value matches input safely without script execution")
        expect(login_input).to_have_value(payload)
    except Exception as e:
        page.screenshot(path="screenshot_edge_case_input_fail.png", full_page=True)
        print(f"[ERROR] Interaction or input validation failed: {e}")
        raise


def test_special_char_injection_login_03_action_and_outcome(page: Page):
    """
    Scenario: Special Character and Injection Resilience in Login Identifier
    Scenario ID: e4d08099-3f54-4238-9d56-abb53fa58c17
    Subtest: Submit Injection Payload & Verify Clean Error Response
    Category: edge_case
    """
    dialog_triggered = []

    def on_dialog(dialog):
        dialog_triggered.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", on_dialog)

    server_errors = []

    def on_response(response):
        if response.status >= 500:
            server_errors.append(f"{response.url} returned {response.status}")

    page.on("response", on_response)

    try:
        print("[STEP 1] Navigate to signin page")
        page.goto("http://localhost:5678/signin", wait_until="networkidle")

        payload = "<script>alert('xss')</script>' OR '1'='1' --"
        print(f"[STEP 2] Fill login identifier with payload: {payload}")
        login_input = page.locator("#emailOrLdapLoginId, input[name='emailOrLdapLoginId'], input[name='email']").first
        login_input.fill(payload)

        print("[STEP 3] Fill password field")
        password_input = page.locator("#password, input[name='password'], input[type='password']").first
        password_input.fill("SamplePassword123!")

        print("[STEP 4] Click Sign in button")
        signin_button = page.locator("button:has-text('Sign in'), button[type='submit']").first
        signin_button.click()

        print("[STEP 5] Wait for response or error message notification")
        page.wait_for_timeout(2000)

        print("[STEP 6] Assert no XSS dialog was executed")
        assert len(dialog_triggered) == 0, f"XSS script executed! Triggered dialogs: {dialog_triggered}"

        print("[STEP 7] Assert no 500 Internal Server Errors occurred")
        assert len(server_errors) == 0, f"Server errors detected: {server_errors}"

        print("[STEP 8] Verify application rejected invalid credentials cleanly or remained on signin page")
        error_banner = page.locator(".el-message--error, .el-notification--error, [role='alert'], :text-matches('Invalid|incorrect|error|failed|does not exist', 'i')")
        
        # Either an explicit error notification is visible or user remains safely on the signin page
        current_url = page.url
        assert "/signin" in current_url or error_banner.count() > 0, "Unexpected redirect or state on invalid payload submission"
        print("[STEP 9] Input safely handled without script execution or 500 server error")
    except Exception as e:
        page.screenshot(path="screenshot_edge_case_outcome_fail.png", full_page=True)
        print(f"[ERROR] Submission outcome verification failed: {e}")
        raise

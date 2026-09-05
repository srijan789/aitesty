import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"
AUTH_USER = "srijan.psn@gmail.com"
AUTH_PASS = "Password1"


@pytest.fixture(autouse=True)
def setup_diagnostics(page: Page, request):
    """Captures console errors, network errors, and takes screenshots on test failure."""
    console_errors = []
    failed_requests = []

    def handle_console(msg):
        if msg.type == "error":
            console_errors.append(f"[{msg.location.get('url', 'unknown')}:{msg.location.get('lineNumber', 0)}] {msg.text}")

    def handle_response(response):
        if response.status >= 400:
            failed_requests.append(f"{response.request.method} {response.url} -> {response.status}")

    page.on("console", handle_console)
    page.on("response", handle_response)

    yield

    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        os.makedirs("screenshots", exist_ok=True)
        screenshot_path = f"screenshots/failure_{request.node.name}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n[FAILURE DIAGNOSTICS] Test '{request.node.name}' failed.")
        print(f"[FAILURE DIAGNOSTICS] Saved failure screenshot to: {screenshot_path}")
        if console_errors:
            print("[FAILURE DIAGNOSTICS] Console Errors detected during test:")
            for err in console_errors:
                print(f"  - {err}")
        if failed_requests:
            print("[FAILURE DIAGNOSTICS] Failed Network Requests (HTTP >= 400):")
            for req in failed_requests:
                print(f"  - {req}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to attach test execution status to node for fixture diagnostic checks."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def handle_login_if_required(page: Page):
    """Helper to handle authentication form if redirected to signin page."""
    if "signin" in page.url or page.locator("input[type='email'], input[name='email']").is_visible():
        print(f"[AUTH] Detected login screen. Authenticating as '{AUTH_USER}'...")
        email_input = page.locator("input[type='email'], input[name='email']").first
        password_input = page.locator("input[type='password'], input[name='password']").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first

        email_input.fill(AUTH_USER)
        password_input.fill(AUTH_PASS)
        submit_btn.click()
        page.wait_for_load_state("networkidle")


def test_initial_application_load_and_core_view(page: Page):
    """
    Scenario ID: 2216a900-0426-463b-a39e-76f026b95f88
    Title: Initial Application Load & Core View Render (Workflows - n8n)
    Priority: P0
    Category: happy_path
    """
    target_url = f"{BASE_URL}/home/workflows"

    # Step 1: Navigate to target URL and verify HTTP response status
    print(f"[STEP 1] Navigate on '{target_url}'")
    response = page.goto(target_url, wait_until="domcontentloaded", timeout=10000)

    assert response is not None, f"Failed to receive response from {target_url}"
    assert response.status < 400, f"Expected successful HTTP status (< 400), got {response.status}"

    # Handle login if n8n redirects unauthenticated session
    handle_login_if_required(page)

    # Ensure page finishes loading
    page.wait_for_load_state("networkidle")

    # Step 2: Assert on page title
    print("[STEP 2] Assert on 'body' -> Page title matches 'Workflows - n8n' or contains n8n branding")
    # n8n document titles typically include 'n8n' or 'Workflows - n8n'
    expect(page).to_have_title(lambda title: "n8n" in title or "Workflows" in title, timeout=5000)

    # Step 3: Assert on primary navigation & layout elements
    print("[STEP 3] Assert on 'header, nav' -> Primary navigation elements rendered")
    # Locate primary UI elements: sidebar navigation, header, or main container
    nav_locator = page.locator("nav, [role='navigation'], [data-test-id='sidebar'], header, aside").first
    expect(nav_locator).to_be_visible(timeout=5000)

    # Verify main content area is rendered and not a blank/error screen
    main_content = page.locator("main, #app, #root, .workflow-list, [data-test-id='resources-list']").first
    expect(main_content).to_be_visible(timeout=5000)

    print("[STEP COMPLETE] Application rendered layout, navigation bar, and primary landing components successfully.")

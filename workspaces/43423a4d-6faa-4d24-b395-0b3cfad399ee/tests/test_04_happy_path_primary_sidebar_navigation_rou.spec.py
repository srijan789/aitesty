import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "https://d2928k9vety1kj.cloudfront.net"
LOGIN_URL = f"{BASE_URL}/sso/login"
USERNAME = "user-3-Team10@velogent.com"
PASSWORD = "F@@OLwY16C"


def login_user(page: Page) -> None:
    """Helper to authenticate user and navigate to initial landing state."""
    page.goto(LOGIN_URL, wait_until="networkidle")
    if "/sso/login" in page.url or page.locator("input[name='email'], input[type='email'], input[name='username']").is_visible():
        email_input = page.locator("input[name='email'], input[type='email'], input[name='username']").first
        password_input = page.locator("input[name='password'], input[type='password']").first
        submit_btn = page.locator("button[type='submit'], button:has-text('Sign In'), button:has-text('Log In')").first

        email_input.fill(USERNAME)
        password_input.fill(PASSWORD)
        submit_btn.click()
        page.wait_for_load_state("networkidle")


def navigate_sidebar(page: Page, link_selector: str, fallback_text: str):
    """Resilient sidebar navigation helper."""
    sidebar_link = page.locator(link_selector).first
    if not sidebar_link.is_visible():
        sidebar_link = page.locator(f"nav a:has-text('{fallback_text}'), aside a:has-text('{fallback_text}')").first
    sidebar_link.click()
    page.wait_for_load_state("networkidle")


def test_primary_sidebar_nav_01_navigate_and_view(page: Page) -> None:
    """
    Scenario: Primary Sidebar Navigation Route Transitions
    Scenario ID: b4cc172f-fd1b-4ee4-a22f-20055e395f30
    Subtest: Initial Navigation & Dashboard View Render
    Category: happy_path
    """
    try:
        print("[STEP 1] Log in and verify initial state on agentflows")
        login_user(page)
        page.goto(f"{BASE_URL}/agentflows", wait_until="networkidle")
        expect(page).to_have_url(re.compile(r"/agentflows"))

        print("[STEP 2] Click Dashboard link and verify navigation to /dashboard/overview")
        navigate_sidebar(page, 'a[href*="/dashboard/overview"], a[href="/dashboard/overview"]', "Dashboard")
        page.wait_for_url(re.compile(r"/dashboard/overview"), timeout=10000)
        expect(page).to_have_url(re.compile(r"/dashboard/overview"))

        print("[STEP 3] Verify Dashboard page contents render without 404/500 errors")
        main_content = page.locator("main, [role='main'], #root, body")
        expect(main_content).not_to_contain_text("404")
        expect(main_content).not_to_contain_text("500 Internal Server Error")
    except Exception as exc:
        page.screenshot(path="screenshot_nav_01_failure.png", full_page=True)
        print(f"[FAILURE] Subtest 01 encountered an error: {exc}")
        raise


def test_primary_sidebar_nav_02_interaction_and_validation(page: Page) -> None:
    """
    Scenario: Primary Sidebar Navigation Route Transitions
    Scenario ID: b4cc172f-fd1b-4ee4-a22f-20055e395f30
    Subtest: Executions and Tools Route Transitions
    Category: happy_path
    """
    try:
        print("[STEP 1] Ensure user is authenticated")
        login_user(page)

        print("[STEP 2] Navigate to Executions route via sidebar")
        navigate_sidebar(page, 'a[href*="/executions"], a[href="/executions"]', "Executions")
        page.wait_for_url(re.compile(r"/executions"), timeout=10000)
        expect(page).to_have_url(re.compile(r"/executions"))

        print("[STEP 3] Navigate to Tools route via sidebar")
        navigate_sidebar(page, 'a[href*="/tools"], a[href="/tools"]', "Tools")
        page.wait_for_url(re.compile(r"/tools"), timeout=10000)
        expect(page).to_have_url(re.compile(r"/tools"))

        print("[STEP 4] Validate Tools page components render")
        main_content = page.locator("main, [role='main'], #root, body")
        expect(main_content).not_to_contain_text("404 Not Found")
    except Exception as exc:
        page.screenshot(path="screenshot_nav_02_failure.png", full_page=True)
        print(f"[FAILURE] Subtest 02 encountered an error: {exc}")
        raise


def test_primary_sidebar_nav_03_action_and_outcome(page: Page) -> None:
    """
    Scenario: Primary Sidebar Navigation Route Transitions
    Scenario ID: b4cc172f-fd1b-4ee4-a22f-20055e395f30
    Subtest: Marketplace / AgentHub Catalog Navigation & Full Cycle Verification
    Category: happy_path
    """
    try:
        print("[STEP 1] Ensure user is authenticated")
        login_user(page)

        print("[STEP 2] Navigate to Marketplaces / AgentHub catalog via sidebar")
        navigate_sidebar(page, 'a[href*="/marketplaces"], a[href="/marketplaces"]', "Marketplace")
        page.wait_for_url(re.compile(r"/marketplaces"), timeout=10000)
        expect(page).to_have_url(re.compile(r"/marketplaces"))

        print("[STEP 3] Cycle back to Agentflows to confirm complete bidirectional route navigation")
        navigate_sidebar(page, 'a[href*="/agentflows"], a[href="/agentflows"]', "Agentflows")
        page.wait_for_url(re.compile(r"/agentflows"), timeout=10000)
        expect(page).to_have_url(re.compile(r"/agentflows"))

        print("[STEP 4] Verify full navigation loop completed successfully without error screens")
        main_content = page.locator("main, [role='main'], #root, body")
        expect(main_content).not_to_contain_text("Application Error")
    except Exception as exc:
        page.screenshot(path="screenshot_nav_03_failure.png", full_page=True)
        print(f"[FAILURE] Subtest 03 encountered an error: {exc}")
        raise

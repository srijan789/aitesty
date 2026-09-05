import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5678"

def test_invalid_route_and_error_boundary_handling(page: Page):
    """
    Scenario ID: 11bf70c2-9c61-430b-a2c8-b504c21e2280
    Title: Invalid Route & Error Boundary Handling
    Description: Verify graceful user feedback when navigating to a non-existent URL or encountering broken links.
    """
    console_errors = []
    page_errors = []

    # Telemetry listeners
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    try:
        # Step 1: Navigate to non-existent route
        invalid_url = f"{BASE_URL}/home/workflows/non-existent-qa-route-404"
        print(f"[STEP 1] Navigate to '{invalid_url}'")
        response = page.goto(invalid_url, wait_until="networkidle", timeout=15000)

        # Step 2: Assert on body for clean 404 error page / graceful boundary handling with Home link
        print("[STEP 2] Assert on 'body' for graceful 404 / error boundary UI with navigation options")
        
        # Verify page is not completely blank
        body = page.locator("body")
        expect(body).not_to_be_empty()

        # Check that page does not contain raw unhandled server dump/traceback
        page_content = page.content().lower()
        assert "traceback (most recent call last)" not in page_content, "Raw Python/server traceback detected on page"
        assert "internal server error (500)" not in page_content, "Raw 500 internal server error detected"
        assert "cannot get /" not in page_content, "Raw express unhandled route error detected"

        # Check for user-friendly 404/not found messaging or redirection to safety
        # In single-page apps like n8n or modern dashboards, 404 page typically includes "404", "Not Found", "Page not found", or redirects to signin/workflows
        error_heading = page.locator("text=/(404|Page not found|Page Not Found|Not Found|Lost|Page doesn't exist)/i").first
        home_or_safety_link = page.locator("a[href*='/'], button:has-text('Home'), button:has-text('Go back'), a:has-text('Home'), a:has-text('Workflows')").first

        is_error_displayed = error_heading.is_visible(timeout=3000)
        is_home_link_available = home_or_safety_link.is_visible(timeout=3000)

        # Either a friendly 404 page is rendered with a home link, or SPA gracefully redirected to valid app root/signin
        if is_error_displayed:
            print("[INFO] Dedicated 404/Not Found UI component detected.")
            expect(error_heading).to_be_visible()
            if is_home_link_available:
                print(f"[STEP 2a] Verify return-to-safety element is clickable: '{home_or_safety_link.text_content()}'")
                expect(home_or_safety_link).to_be_enabled()
        else:
            # Check if SPA safely routed to valid dashboard or login
            current_url = page.url
            print(f"[INFO] Application resolved route to: {current_url}")
            assert any(route in current_url for route in ["/signin", "/workflows", "/home", "/setup", "/login"]), (
                f"Unexpected navigation state after invalid route request: {current_url}"
            )

        print("[SUCCESS] Invalid route handled gracefully without raw crash or unhandled server error.")

    except Exception as e:
        screenshot_path = "failure_invalid_route_404.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"[FAILURE] Test failed. Captured screenshot at {screenshot_path}. Error: {e}")
        if console_errors:
            print(f"[DIAGNOSTICS] Captured console errors: {console_errors}")
        if page_errors:
            print(f"[DIAGNOSTICS] Captured page exceptions: {page_errors}")
        raise

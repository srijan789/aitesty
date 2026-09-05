# Test Plan: E2E Automated Test Plan for final aivar demo (v1)

Version: 1 | Status: active
Generated: 2026-09-05 14:27:55 UTC

## Discovered Scenarios

### ✅ Happy Path Scenarios

#### [P0] User Authentication via SSO Login Flow `(marked_for_automation)`
Verify that a user with valid credentials can successfully authenticate and is redirected to the Agentflows dashboard.

**Preconditions:** User is on the SSO login page (/sso/login) and not authenticated.

**Execution Steps:**
1. Navigate on `https://d2928k9vety1kj.cloudfront.net/sso/login` -> Login form rendered with username and password inputs.
2. Fill on `#login-username` -> Username input contains valid email.
3. Fill on `#login-password` -> Password input contains valid password.
4. Click on `button:has-text("Sign in")` -> Auth request sent and user redirected to /agentflows.

**Expected Output:** User is authenticated and redirected to /agentflows with workspace and navigation elements loaded.

**Pass / Fail Criteria:** PASS: HTTP POST to /api/v1/auth/login returns 200 OK and browser redirects to /agentflows. FAIL: Authentication fails or user remains stuck on /sso/login.

#### [P1] Primary Sidebar Navigation Route Transitions `(marked_for_automation)`
Verify that authenticated users can switch between primary sections using the main sidebar navigation.

**Preconditions:** User is logged in and on /agentflows.

**Execution Steps:**
1. Click on `a[href="/dashboard/overview"]` -> Navigates to /dashboard/overview with Overview and Cost metrics.
2. Click on `a[href="/executions"]` -> Navigates to /executions with execution history table.
3. Click on `a[href="/tools"]` -> Navigates to /tools with tool list and search options.
4. Click on `a[href="/marketplaces"]` -> Navigates to /marketplaces with AgentHub catalog.

**Expected Output:** Navigation seamlessly loads selected routes (Dashboard, Agentflows, Executions, Tools, AgentHub, Knowledge Base) without errors.

**Pass / Fail Criteria:** PASS: Clicking sidebar links updates the URL and renders corresponding header and page components. FAIL: White screen, 404/500 errors, or failed transitions.

#### [P2] View Layout Switching (Card vs List View) `(marked_for_automation)`
Verify toggling view layouts between Card and List presentation modes in Agentflows and Tools views.

**Preconditions:** User is on /agentflows or /tools view.

**Execution Steps:**
1. Navigate on `/agentflows` -> Agentflows view loaded.
2. Click on `button:has-text("list")` -> Layout renders items in list table format.
3. Click on `button:has-text("card")` -> Layout renders items in card grid format.

**Expected Output:** Content display switches between grid cards and list rows smoothly.

**Pass / Fail Criteria:** PASS: Active view state toggles between card and list layout without data loss. FAIL: UI does not react or layout is broken.

#### [P1] Dashboard Tab Switching (Overview vs Cost) `(marked_for_automation)`
Verify Dashboard metrics tab switching between Overview and Cost views.

**Preconditions:** User is authenticated and on /dashboard/overview.

**Execution Steps:**
1. Navigate on `/dashboard/overview` -> Dashboard loaded with Overview tab active.
2. Click on `button:has-text("Cost")` -> Cost tab is selected and Cost metrics/breakdown panel is displayed.
3. Click on `button:has-text("Overview")` -> Overview tab is selected and Overview metrics are displayed.

**Expected Output:** Dashboard tabs switch properly, updating charts and metric panels for the selected tab.

**Pass / Fail Criteria:** PASS: Switching tabs loads corresponding metrics without console errors. FAIL: Charts fail to render or tabs remain inactive.

---

### ⚠️ Edge Cases & Boundary Conditions

#### [P2] Search Field Query and Special Characters Handling `(marked_for_automation)`
Verify search input filtering behavior across views (Agentflows, Tools, AgentHub) with special characters and empty values.

**Preconditions:** User is authenticated on /tools.

**Execution Steps:**
1. Navigate on `/tools` -> Tools page loaded.
2. Fill on `input[type="search"]` -> Search query populated.
3. Fill on `input[type="search"]` -> Search safely evaluated without syntax errors or unhandled exceptions.

**Expected Output:** Search query handles special characters safely without application crashes or XSS, displaying appropriate matches or empty state.

**Pass / Fail Criteria:** PASS: Input accepts text, triggers search filtering, handles special chars ('<script>', '`', '%'), and shows zero/relevant results. FAIL: Uncaught JS error or application freeze.

#### [P1] Permission State and Action Button Disabled State Verification `(marked_for_automation)`
Verify RBAC/Permission state enforcement on action buttons (e.g., disabled 'Add New' or 'Create' buttons when permissions/limits apply).

**Preconditions:** User is authenticated with default workspace permissions on /agentflows.

**Execution Steps:**
1. Navigate on `/agentflows` -> Agentflows page rendered.
2. Assert on `button:has-text("Add New")` -> Button has disabled attribute / Mui-disabled class.
3. Navigate on `/tools` -> Tools page rendered.
4. Assert on `button:has-text("Create")` -> Create button has disabled attribute when unauthorized.

**Expected Output:** Buttons properly reflect authorization state with disabled attributes and clear tooltip/indication when user lacks creation permissions.

**Pass / Fail Criteria:** PASS: Disabled buttons cannot be triggered to perform invalid API mutations and have proper ARIA disabled states. FAIL: Clicking disabled button causes unhandled client or server exceptions.

---

### 🛑 Error Handling & Negative Flows

#### [P0] Authentication Failure with Invalid Credentials `(marked_for_automation)`
Verify that submitting invalid credentials displays an error message and prevents unauthorized access.

**Preconditions:** User is on /sso/login.

**Execution Steps:**
1. Navigate on `/sso/login` -> Login page displays.
2. Fill on `#login-username` -> Field filled with non-existent user.
3. Fill on `#login-password` -> Field filled with invalid password.
4. Click on `button:has-text("Sign in")` -> Error banner/alert is displayed indicating invalid credentials.

**Expected Output:** Login request fails with 401 Unauthorized or error toast/alert, retaining user on login screen.

**Pass / Fail Criteria:** PASS: Error message/feedback is presented, no session is established, URL remains /sso/login. FAIL: System allows access or throws an unhandled exception crash.

#### [P2] Handling of Invalid Routes and 404 States `(marked_for_automation)`
Verify application behavior when navigating to non-existent route or invalid URL path.

**Preconditions:** User is authenticated in the application.

**Execution Steps:**
1. Navigate on `/non-existent-route-qa-test` -> 404 Not Found view or graceful fallback route rendered.
2. Assert on `a[href="/dashboard/overview"]` -> Sidebar and header navigation remain operational.

**Expected Output:** Application presents a graceful 404 Not Found page or redirects to dashboard without crashing.

**Pass / Fail Criteria:** PASS: Clean 404 page or fallback redirect with navigation options intact. FAIL: Uncaught JavaScript error, blank white page, or broken layout.

---

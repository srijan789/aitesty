# Test Plan: Automated Test Plan for n8n demo (v7)

Version: 7 | Status: active
Generated: 2026-09-05 11:53:46 UTC

## Discovered Scenarios

### ✅ Happy Path Scenarios

#### [P0] Successful User Sign-In with Valid Credentials `(automated)`
Verify that a user can successfully authenticate using valid email and password credentials.

**Preconditions:** User is logged out on http://localhost:5678/signin.

**Execution Steps:**
1. Navigate on `http://localhost:5678/signin` -> Sign in page renders with email and password inputs.
2. Fill on `#emailOrLdapLoginId` -> Email input contains srijan.psn@gmail.com.
3. Fill on `#password` -> Password input contains Password1.
4. Click on `button:has-text("Sign in")` -> Authentication request succeeds and redirects to dashboard/assistant.

**Expected Output:** User is authenticated and redirected to the application onboard/dashboard view.

**Pass / Fail Criteria:** PASS if HTTP 200/redirect occurs and user lands on dashboard or assistant view. FAIL if error message displays or remains on sign-in page.

#### [P1] Navigate to Forgot Password Flow `(automated)`
Verify navigation to forgot password view and presence of recovery instructions/inputs.

**Preconditions:** User is unauthenticated on /signin.

**Execution Steps:**
1. Navigate on `http://localhost:5678/signin` -> Sign-in page loads with forgot password link.
2. Click on `a[href='/forgot-password']` -> Navigates to /forgot-password route.

**Expected Output:** Forgot password route is reachable and displays recovery interface or redirection.

**Pass / Fail Criteria:** PASS if forgot password view loads with 200 HTTP status and proper recovery controls. FAIL if 404 or uncaught exception.

#### [P0] Create and Initialize New Workflow Canvas `(automated)`
Verify initialization of a new workflow canvas from navigation.

**Preconditions:** User is authenticated in n8n.

**Execution Steps:**
1. Navigate on `http://localhost:5678/workflow/new` -> Navigates to workflow creation endpoint.
2. Assert on `button:has-text("Publish")` -> Workflow editor is visible with Publish button and canvas.

**Expected Output:** A new empty workflow is generated with canvas, editor controls, and unique workflow ID.

**Pass / Fail Criteria:** PASS if /workflow/new initializes a workflow canvas with Editor/Executions tabs and Publish button. FAIL if canvas fails to render.

#### [P1] Access Settings Configuration Dashboard `(automated)`
Verify access to Settings overview and sub-navigation links.

**Preconditions:** User is authenticated with administrative privileges.

**Execution Steps:**
1. Navigate on `http://localhost:5678/settings` -> Settings page loads successfully.
2. Assert on `a[href='/settings/users']` -> Settings sub-links (Users, API, Usage) are visible.

**Expected Output:** Settings dashboard renders with navigation tabs for Personal, Users, API, SSO, and Security.

**Pass / Fail Criteria:** PASS if settings dashboard and sidebar options render correctly. FAIL if settings route throws 500 or blank screen.

#### [P2] AI Assistant Onboarding and Dismissal `(automated)`
Verify AI Assistant onboarding view and options to setup or postpone.

**Preconditions:** User is authenticated on /assistant.

**Execution Steps:**
1. Navigate on `http://localhost:5678/assistant` -> AI Assistant onboarding screen appears.
2. Click on `button:has-text("Set up later in Settings")` -> Redirects to main workflows view.

**Expected Output:** AI Assistant banner displays option to 'Get started' or 'Set up later in Settings'.

**Pass / Fail Criteria:** PASS if clicking 'Set up later in Settings' dismisses the prompt and redirects to /home/workflows. FAIL if dialog cannot be dismissed.

#### [P1] Workflow View Tab Switching (Editor vs Executions) `(automated)`
Verify navigation between Workflow canvas tabs (Editor, Executions, Evaluations).

**Preconditions:** User is on a workflow view (/workflow/new).

**Execution Steps:**
1. Navigate on `http://localhost:5678/workflow/new` -> Workflow canvas is displayed with tab bar.
2. Click on `button:has-text("Executions")` -> Executions log view is displayed.
3. Click on `button:has-text("Editor")` -> Editor canvas view is restored.

**Expected Output:** User can switch seamlessly between Editor and Executions sub-views.

**Pass / Fail Criteria:** PASS if tab clicks change active view state without page reloads or errors. FAIL if switching tabs results in UI lockup.

---

### ⚠️ Edge Cases & Boundary Conditions

#### [P1] Empty Form Submission Validation on Sign-In `(automated)`
Verify client/server validation behavior when submitting empty credentials on the sign-in form.

**Preconditions:** User is on /signin page.

**Execution Steps:**
1. Navigate on `http://localhost:5678/signin` -> Sign in inputs are empty.
2. Click on `button:has-text("Sign in")` -> Validation triggers indicating fields are required.

**Expected Output:** Form validation prevents submission or highlights missing required fields without unhandled exceptions.

**Pass / Fail Criteria:** PASS if required field validation triggers and no login request is dispatched. FAIL if 500 error occurs.

#### [P1] Special Character and Injection Resilience in Login Identifier `(automated)`
Verify application resilience when entering special characters and SQL/XSS payloads into the login identifier.

**Preconditions:** User is on /signin page.

**Execution Steps:**
1. Navigate on `http://localhost:5678/signin` -> Sign-in page loads.
2. Fill on `#emailOrLdapLoginId` -> Special characters and quotes accepted into input safely.
3. Fill on `#password` -> Password filled.
4. Click on `button:has-text("Sign in")` -> Clean rejection response without script execution.

**Expected Output:** Input is safely sanitized or validated without executing scripts or causing 500 server errors.

**Pass / Fail Criteria:** PASS if input is rejected safely with invalid credential notification and no script executes. FAIL if XSS executes or 500 internal server error is returned.

#### [P2] Input Boundary and Overflow Handling on Sign-In Inputs `(automated)`
Verify sign-in input boundary testing with maximum length strings (>256 characters).

**Preconditions:** User is on /signin page.

**Execution Steps:**
1. Navigate on `http://localhost:5678/signin` -> Sign in page loads.
2. Fill on `#emailOrLdapLoginId` -> Overly long email string entered.
3. Click on `button:has-text("Sign in")` -> Handled gracefully with validation error.

**Expected Output:** Inputs handle long string lengths without UI distortion or frontend crashing.

**Pass / Fail Criteria:** PASS if UI remains responsive, text wraps or truncates cleanly, and server returns 400/401 cleanly. FAIL if UI layout breaks or browser freezes.

---

### 🛑 Error Handling & Negative Flows

#### [P0] Sign-In Rejection with Invalid Password `(automated)`
Verify that authentication fails gracefully when incorrect password is provided.

**Preconditions:** User is on /signin page.

**Execution Steps:**
1. Navigate on `http://localhost:5678/signin` -> Sign in form is visible.
2. Fill on `#emailOrLdapLoginId` -> Email is entered.
3. Fill on `#password` -> Invalid password is typed.
4. Click on `button:has-text("Sign in")` -> Error notification is displayed indicating invalid credentials.

**Expected Output:** User remains on signin page with an explicit error notification and no session is created.

**Pass / Fail Criteria:** PASS if an authentication error notification appears and route remains on /signin. FAIL if unauthorized access is granted or page crashes.

#### [P2] Graceful 404 Error Handling for Invalid Routes `(automated)`
Verify handling of non-existent application routes (404 Page Not Found).

**Preconditions:** User is authenticated.

**Execution Steps:**
1. Navigate on `http://localhost:5678/non-existent-route-404` -> 404 Not Found view is shown.
2. Click on `button:has-text("Go back")` -> Returns user back to previous valid view.

**Expected Output:** User is presented with a user-friendly 404 page with a 'Go back' navigation option.

**Pass / Fail Criteria:** PASS if 404 error page renders cleanly with a working 'Go back' button. FAIL if white-screen crash or unhandled console errors occur.

#### [P0] Unauthorized Access Redirection to Login `(automated)`
Verify session redirect behavior when accessing authenticated routes without a valid session.

**Preconditions:** User session is cleared/logged out.

**Execution Steps:**
1. Navigate on `http://localhost:5678/settings` -> Application intercepts request and redirects to /signin?redirect=%2Fsettings.
2. Assert on `#emailOrLdapLoginId` -> Login form is presented.

**Expected Output:** Unauthenticated access redirects to /signin with original path encoded in redirect query parameter.

**Pass / Fail Criteria:** PASS if unauthorized request is redirected to /signin?redirect=... FAIL if protected data is leaked or page stays blank.

---

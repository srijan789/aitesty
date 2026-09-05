import json
import time
import pytest
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun
from app.core.telemetry import classify_failure, FailureClassification, FailureSubType
from app.core.report_generator import generate_html_report
from app.core.test_runner import TestRunner

@pytest.fixture
def app():
    app = create_app("config.TestingConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_classify_failure_automation_locator_timeout():
    err_msg = "playwright._impl._errors.TimeoutError: Page.click: Timeout 5000ms exceeded. waiting for locator('#submit-btn')"
    tb = "Traceback ... Page.click: Timeout 5000ms exceeded."
    res = classify_failure(err_msg, tb, page_url="http://app/checkout")
    
    assert res["classification"] == FailureClassification.AUTOMATION_FAILURE
    assert res["subtype"] == FailureSubType.LOCATOR_TIMEOUT
    assert res["healing_action"] == "HEAL_LOCATOR"
    assert "suggested_actions" in res["healing_context"]

def test_classify_failure_app_defect_server_500():
    err_msg = "Expected dashboard to render"
    network_logs = [
        {"type": "response", "status": 500, "url": "http://app/api/auth", "body_preview": "Internal Database Error"}
    ]
    res = classify_failure(err_msg, network_logs=network_logs)
    
    assert res["classification"] == FailureClassification.APP_DEFECT
    assert res["subtype"] == FailureSubType.HTTP_SERVER_ERROR
    assert res["healing_action"] == "ESCALATE_BUG"

def test_classify_failure_app_defect_assertion_error():
    err_msg = "AssertionError: expected 'Welcome, Alice' but got 'Error: Invalid Token'"
    tb = "Traceback ... AssertionError: expected 'Welcome, Alice'"
    res = classify_failure(err_msg, tb)
    
    assert res["classification"] == FailureClassification.APP_DEFECT
    assert res["subtype"] == FailureSubType.ASSERTION_FAILED

def test_report_generation_html():
    results = {
        "summary": {
            "total": 3,
            "passed": 2,
            "failed": 1,
            "skipped": 0,
            "duration_ms": 3200,
            "app_defects": 1,
            "automation_failures": 0,
        },
        "tests": [
            {
                "test_name": "test_login_flow",
                "status": "passed",
                "duration_ms": 1200,
                "steps": [{"step_number": 1, "action": "Navigate", "target": "/login", "outcome": "OK", "duration_ms": 100}],
            },
            {
                "test_name": "test_checkout_bug",
                "status": "failed",
                "duration_ms": 2000,
                "error_details": {
                    "error_message": "Server returned 500",
                    "classification": {
                        "classification": "APP_DEFECT",
                        "subtype": "HTTP_SERVER_ERROR",
                        "summary": "Application 500",
                        "root_cause_analysis": "Database crashed",
                        "healing_action": "ESCALATE_BUG",
                    }
                }
            }
        ]
    }
    html = generate_html_report(results, project_name="Acme Web", target_url="http://acme.com", run_id="run-123")
    assert "Acme Web" in html
    assert "APP DEFECT (BUG)" in html
    assert "Pass Rate" in html
    assert "test_login_flow" in html

from unittest.mock import patch, MagicMock

def test_test_runner_suite_and_file_execution(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    conftest = tmp_path / "conftest.py"
    conftest.write_text("""
import pytest
from unittest.mock import MagicMock
@pytest.fixture
def page():
    return MagicMock()
""", encoding="utf-8")
    
    # Create two test spec files
    spec1 = tests_dir / "test_auth.spec.py"
    spec1.write_text("""
def test_login_success(page):
    \"\"\"
    Scenario ID: sc-auth-1
    Category: happy_path
    \"\"\"
    print("[STEP 1] Navigate to http://example.com")
    print("[STEP 2] Verify login")

def test_logout(page):
    \"\"\"
    Scenario ID: sc-auth-2
    Category: happy_path
    \"\"\"
    print("[STEP 1] Navigate to http://example.com")
""", encoding="utf-8")

    spec2 = tests_dir / "test_boundary.spec.py"
    spec2.write_text("""
def test_long_input(page):
    \"\"\"
    Scenario ID: sc-bound-1
    Category: edge_case
    \"\"\"
    print("[STEP 1] Enter 1000 characters")
""", encoding="utf-8")

    runner = TestRunner(
        workspace_dir=str(tmp_path),
        project_id="proj-exec",
        run_id="run-exec-1",
        target_url="http://example.com",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("requests.get", return_value=mock_resp):
        # 1. Run entire suite
        suite_res = runner.execute()
        assert suite_res["summary"]["total"] == 3
        assert suite_res["summary"]["passed"] == 3
        assert (tmp_path / "runs" / "run-exec-1" / "report.html").exists()

        # 2. Run individual file
        file_res = runner.execute(target_file="tests/test_boundary.spec.py")
        assert file_res["summary"]["total"] == 1
        assert file_res["summary"]["passed"] == 1


def test_test_runner_detects_offline_server_as_app_defect(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    spec = tests_dir / "test_auth.spec.py"
    spec.write_text("""
def test_login_flow(page):
    \"\"\"
    Scenario ID: sc-offline-1
    Category: happy_path
    \"\"\"
    print("[STEP 1] Navigate to http://127.0.0.1:59999")
""", encoding="utf-8")

    runner = TestRunner(
        workspace_dir=str(tmp_path),
        project_id="proj-offline",
        run_id="run-offline-1",
        target_url="http://127.0.0.1:59999",
    )

    # Server at port 59999 is offline; execute should detect it and fail with APP_DEFECT
    results = runner.execute()
    assert results["summary"]["total"] == 1
    assert results["summary"]["passed"] == 0
    assert results["summary"]["failed"] == 1
    assert results["summary"]["app_defects"] == 1

    first_test = results["tests"][0]
    assert first_test["status"] == "failed"
    err_class = first_test["error_details"]["classification"]
    assert err_class["classification"] == FailureClassification.APP_DEFECT
    assert err_class["subtype"] == FailureSubType.SERVER_UNREACHABLE
    assert "offline or unreachable" in first_test["error_details"]["error_message"].lower()

def test_api_generate_and_execute_tests(client, app):
    # Setup project & test plan
    with app.app_context():
        p = Project(name="API Test", target_url="http://example.com", auth_type="none")
        db.session.add(p)
        db.session.commit()
        project_id = p.id

        plan = TestPlan(project_id=project_id, version=1, status="active")
        db.session.add(plan)
        db.session.flush()

        tc = TestCase(test_plan_id=plan.id, title="API Scenario 1", status="marked_for_automation")
        db.session.add(tc)
        db.session.commit()

    # Call POST /api/projects/<id>/generate-tests
    res_gen = client.post(f"/api/projects/{project_id}/generate-tests")
    assert res_gen.status_code == 202
    data_gen = res_gen.get_json()
    assert data_gen["success"] is True
    gen_run_id = data_gen["run_id"]

    # Wait briefly for generator task
    time.sleep(0.5)

    # Call POST /api/projects/<id>/execute-tests
    res_exec = client.post(f"/api/projects/{project_id}/execute-tests", json={})
    assert res_exec.status_code == 202
    data_exec = res_exec.get_json()
    assert data_exec["success"] is True
    exec_run_id = data_exec["run_id"]

    time.sleep(0.5)

    # Call GET /api/runs/<run_id>/report
    res_report = client.get(f"/api/runs/{exec_run_id}/report")
    assert res_report.status_code == 200

    # Call GET /api/runs/<run_id>/report/html
    res_html = client.get(f"/api/runs/{exec_run_id}/report/html")
    assert res_html.status_code == 200
    assert b"Aitesty" in res_html.data

    # Call GET /api/runs/<run_id>/logs/raw
    res_raw_logs = client.get(f"/api/runs/{exec_run_id}/logs/raw")
    assert res_raw_logs.status_code == 200
    assert isinstance(res_raw_logs.data.decode("utf-8"), str)


def test_telemetry_diagnostic_logs_and_healing_context():
    from app.core.telemetry import TestTelemetryLogger
    logger = TestTelemetryLogger(test_name="test_login_subtest")
    logger.log_debug("DEBUG", "Connecting to Playwright Chromium instance")
    logger.log_console("info", "Form rendered onto viewport", "bundle.js:42")
    logger.log_network("POST", "http://example.com/api/login", 200, 120)
    
    candidates = [
        {"tag": "button", "id": "btn-login", "name": "loginBtn", "text": "Sign In", "role": "button", "type": "submit", "testid": "login-button"},
        {"tag": "input", "id": "username-input", "name": "user", "text": "", "role": "", "type": "text", "testid": "username-field"},
    ]
    logger.set_dom_context("<html><body><button id='btn-login'>Sign In</button></body></html>", candidates)

    err = "playwright._impl._errors.TimeoutError: Page.click: Timeout 5000ms exceeded waiting for locator('#submit-btn')"
    tb = "Traceback ... Page.click: Timeout 5000ms exceeded."
    logger.mark_failed(err, tb, page_url="http://example.com/login")

    data = logger.to_dict()
    assert data["status"] == "failed"
    assert len(data["debug_logs"]) >= 1
    assert len(data["console_messages"]) == 1
    assert len(data["network_events"]) == 1
    assert len(data["element_candidates"]) == 2

    # Verify healing context and alternative selectors
    err_det = data["error_details"]
    assert err_det["classification"]["classification"] == FailureClassification.AUTOMATION_FAILURE
    assert len(err_det["alternative_selectors"]) > 0
    assert "[data-testid='login-button']" in err_det["alternative_selectors"]
    assert err_det["suggested_fix"] is not None
    assert err_det["healing_context"] is not None
    assert err_det["healing_context"]["matched_element"]["id"] == "btn-login"


def test_runner_targeted_files_and_test_names(tmp_path):
    from unittest.mock import patch, MagicMock
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    spec1 = tests_dir / "test_auth.spec.py"
    spec1.write_text("""
def test_01_navigate_auth(page):
    \"\"\"
    Subtest: Navigate to Auth
    Scenario ID: sc-auth
    \"\"\"
    print("[STEP 1] Navigate to http://example.com/auth")

def test_02_submit_auth(page):
    \"\"\"
    Subtest: Submit Auth
    Scenario ID: sc-auth
    \"\"\"
    print("[STEP 1] Submit credentials")
""", encoding="utf-8")

    spec2 = tests_dir / "test_cart.spec.py"
    spec2.write_text("""
def test_01_view_cart(page):
    \"\"\"
    Subtest: View Cart
    Scenario ID: sc-cart
    \"\"\"
    print("[STEP 1] Navigate to http://example.com/cart")
""", encoding="utf-8")

    runner = TestRunner(
        workspace_dir=str(tmp_path),
        project_id="proj-targeted",
        run_id="run-targeted-1",
        target_url="http://example.com",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "OK"

    with patch("requests.get", return_value=mock_resp):
        # 1. Target single test function across files
        res1 = runner.execute(target_test_names=["test_01_navigate_auth"])
        assert res1["summary"]["total"] == 1
        assert res1["tests"][0]["test_name"] == "test_01_navigate_auth"

        # 2. Target specific file only
        res2 = runner.execute(target_files=["tests/test_cart.spec.py"])
        assert res2["summary"]["total"] == 1
        assert res2["tests"][0]["test_name"] == "test_01_view_cart"

        # 3. Target multiple specific files
        res3 = runner.execute(target_files=["tests/test_auth.spec.py", "tests/test_cart.spec.py"])
        assert res3["summary"]["total"] == 3
        assert "subtests_per_test" in res3["summary"]
        assert len(res3["summary"]["subtests_per_test"]) == 2
        breakdown = {item["file_name"]: item["subtests_total"] for item in res3["summary"]["subtests_per_test"]}
        assert breakdown["test_auth.spec.py"] == 2
        assert breakdown["test_cart.spec.py"] == 1

def test_classify_failure_with_actual_message():
    err_msg = "AssertionError: expected 'Dashboard' but actual: 'Login'"
    tb = "Traceback (most recent call last):\n  File 'test.py', line 10, in test_foo\n    assert False\nAssertionError: expected 'Dashboard' but actual: 'Login'"
    res = classify_failure(err_msg, tb)
    assert res["classification"] == FailureClassification.APP_DEFECT
    assert res["subtype"] == FailureSubType.ASSERTION_FAILED
    assert res["healing_context"]["actual"] == "'Login'"
    assert res["healing_context"]["expected"] == "'Dashboard'"

def test_classify_failure_with_word_actual_does_not_crash():
    # Playwright assertion message containing the word 'actual'
    err_msg = "AssertionError: Locator.expect: Element is actual value mismatch"
    tb = "Traceback ... AssertionError: Locator.expect: Element is actual value mismatch"
    # Previously crashed with AttributeError: 'NoneType' object has no attribute 'strip'
    res = classify_failure(err_msg, tb)
    assert res["classification"] == FailureClassification.APP_DEFECT
    assert res["subtype"] == FailureSubType.ASSERTION_FAILED

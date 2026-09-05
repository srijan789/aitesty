import json
import shutil
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun
from app.core.e2e_agent import EndToEndAgent, TestPlanReviewer
from app.core.task_runner import task_runner
from app.agents.base import DiscoveredScenario
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        task_runner.wait_for_all_tasks(timeout=2.0)
        db.session.remove()
        db.drop_all()
        if Path(app.config["WORKSPACES_ROOT"]).exists():
            shutil.rmtree(app.config["WORKSPACES_ROOT"], ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


def test_test_plan_reviewer_approval_and_rejection(app):
    """Test TestPlanReviewer filters invalid scenarios and approves valid ones."""
    with app.app_context():
        project = Project(
            name="Reviewer Test Project",
            target_url="https://review.example.com",
            auth_type="none",
        )
        db.session.add(project)
        db.session.commit()

        plan = TestPlan(
            project_id=project.id,
            version=1,
            status="active",
            summary="Reviewer Plan",
        )
        db.session.add(plan)
        db.session.commit()

        # Add valid scenario
        tc1 = TestCase(
            test_plan_id=plan.id,
            title="Valid Login Flow",
            category="happy_path",
            description="Valid user logs in",
            expected_result="User redirected to dashboard",
            pass_fail_criteria="PASS: Dashboard renders\nFAIL: Error shown",
            status="pending_review",
        )
        tc1.set_steps([{"step_number": 1, "action": "Navigate", "target_element": "/login", "expected_outcome": "Form"}])
        db.session.add(tc1)

        # Add invalid scenario (empty steps)
        tc2 = TestCase(
            test_plan_id=plan.id,
            title="Empty Steps Scenario",
            category="edge_case",
            description="No steps provided",
            expected_result="Something happens",
            status="pending_review",
        )
        tc2.set_steps([])
        db.session.add(tc2)

        # Add duplicate scenario
        tc3 = TestCase(
            test_plan_id=plan.id,
            title="Valid Login Flow",
            category="happy_path",
            description="Duplicate title",
            expected_result="User redirected to dashboard",
            status="pending_review",
        )
        tc3.set_steps([{"step_number": 1, "action": "Click", "target_element": "button", "expected_outcome": "Clicked"}])
        db.session.add(tc3)

        db.session.commit()

        logs = []
        summary = TestPlanReviewer.review_and_approve(
            project.id, plan.id, lambda lvl, msg, meta=None: logs.append((lvl, msg))
        )

        assert summary["total_reviewed"] == 3
        assert summary["approved"] == 1
        assert summary["rejected"] == 2
        assert tc1.id in summary["approved_ids"]

        db.session.refresh(tc1)
        db.session.refresh(tc2)
        db.session.refresh(tc3)

        assert tc1.status == "marked_for_automation"
        assert tc2.status == "rejected"
        assert tc3.status == "rejected"


def test_project_create_with_auto_run_e2e(client, app):
    """Test creating a project with auto_run_e2e automatically queues E2E agent."""
    with patch("app.core.task_runner.TaskRunner.submit_task", return_value=True):
        res = client.post(
            "/projects",
            data={
                "name": "Auto E2E App",
                "target_url": "https://autoe2e.test",
                "auth_type": "none",
                "crawl_depth": 2,
                "max_pages": 8,
                "target_test_count": 12,
                "auto_run_e2e": "true",
            },
            follow_redirects=True,
        )
        assert res.status_code == 200

        with app.app_context():
            project = Project.query.filter_by(name="Auto E2E App").first()
            assert project is not None

            # Verify an e2e_pipeline run was queued/started
            e2e_run = TestRun.query.filter_by(project_id=project.id, run_type="e2e_pipeline").first()
            assert e2e_run is not None
            assert e2e_run.trigger == "project_created"


def test_api_e2e_trigger_and_status(client, app):
    """Test triggering E2E agent via REST API and polling e2e-status endpoint."""
    with patch("app.core.task_runner.TaskRunner.submit_task", return_value=True):
        # Create project
        client.post(
            "/projects",
            data={
                "name": "API E2E Project",
                "target_url": "https://api-e2e.test",
                "auth_type": "none",
            },
            follow_redirects=True,
        )

        with app.app_context():
            project = Project.query.filter_by(name="API E2E Project").first()
            proj_id = project.id

        # Check status before run
        res_status0 = client.get(f"/api/projects/{proj_id}/e2e-status")
        assert res_status0.status_code == 200
        assert res_status0.get_json()["has_e2e_run"] is False

        # Trigger E2E pipeline
        res = client.post(
            f"/api/projects/{proj_id}/e2e",
            json={
                "crawl_depth": 2,
                "max_pages": 10,
                "target_test_count": 12,
                "exploration_strategy": "balanced",
            },
        )
        assert res.status_code == 202
        data = res.get_json()
        assert data["success"] is True
        assert "run_id" in data

        # Check status after run
        res_status1 = client.get(f"/api/projects/{proj_id}/e2e-status")
        assert res_status1.status_code == 200
        status_data = res_status1.get_json()
        assert status_data["has_e2e_run"] is True
        assert status_data["run_id"] == data["run_id"]


def test_e2e_agent_full_pipeline_happy_path(app):
    """Test full EndToEndAgent pipeline execution without failures (zero healing needed)."""
    with app.app_context():
        project = Project(
            name="Full Pipeline App",
            target_url="https://fullpipeline.test",
            auth_type="none",
            crawl_depth=2,
            max_pages=10,
            target_test_count=12,
        )
        db.session.add(project)
        db.session.commit()

        run = TestRun(
            project_id=project.id,
            run_type="e2e_pipeline",
            trigger="manual",
            status="queued",
        )
        db.session.add(run)
        db.session.commit()

        agent = EndToEndAgent()
        cancel_event = MagicMock()
        cancel_event.is_set.return_value = False

        mock_passing_summary = {
            "total": 12,
            "passed": 12,
            "failed": 0,
            "tests": [{"name": f"test_mock_scenario_{i}", "status": "passed"} for i in range(1, 13)],
            "duration_ms": 250,
        }

        with patch("app.core.test_runner.TestRunner.execute", return_value={"summary": mock_passing_summary}):
            agent.run_pipeline(
                run_id=run.id,
                cancel_event=cancel_event,
                project_id=project.id,
                crawl_depth=2,
                max_pages=8,
                target_test_count=12,
            )

        db.session.refresh(run)
        assert run.status == "completed"
        stats = run.get_summary_stats()
        assert stats["stage"] == "completed"
        assert stats["progress_percent"] == 100

        # Stage 1: Exploration
        assert stats["exploration"]["total_scenarios"] >= 12
        # Stage 2: Review
        assert stats["review"]["approved"] >= 12
        # Stage 3: Generation
        assert stats["generation"]["scenarios_automated"] >= 12
        # Stage 4: Execution
        assert "execution" in stats
        # Stage 5: Healing (not needed since mock runner passes)
        assert stats["healing"]["max_iterations"] == 2
        assert stats["healing"]["iterations_run"] == 0


def test_e2e_agent_healing_loop_capped_at_two(app):
    """Test that self-healing loop runs at most 2 times when failures persist."""
    with app.app_context():
        project = Project(
            name="Healing Cap App",
            target_url="https://healingcap.test",
            auth_type="none",
            crawl_depth=2,
            max_pages=5,
            target_test_count=12,
        )
        db.session.add(project)
        db.session.commit()

        run = TestRun(
            project_id=project.id,
            run_type="e2e_pipeline",
            trigger="manual",
            status="queued",
        )
        db.session.add(run)
        db.session.commit()

        agent = EndToEndAgent()
        cancel_event = MagicMock()
        cancel_event.is_set.return_value = False

        # Mock TestRunner.execute to always report 1 failing test with automation failure
        failing_exec_result = {
            "summary": {"total": 3, "passed": 2, "failed": 1, "duration_ms": 120},
            "tests": [
                {
                    "test_name": "test_login_submit",
                    "scenario_title": "User Authentication Flow",
                    "status": "failed",
                    "error_message": "Timeout 5000ms waiting for locator('button#submit')",
                    "traceback": "TimeoutError: locator('button#submit')",
                    "failure_classification": "AUTOMATION_FAILURE",
                    "subtype": "LOCATOR_TIMEOUT",
                }
            ],
        }

        with patch("app.core.test_runner.TestRunner.execute", return_value=failing_exec_result):
            agent.run_pipeline(
                run_id=run.id,
                cancel_event=cancel_event,
                project_id=project.id,
                crawl_depth=2,
                max_pages=5,
                target_test_count=12,
            )

        db.session.refresh(run)
        assert run.status == "completed"
        stats = run.get_summary_stats()

        # Verify healing strictly capped at 2 iterations
        assert stats["healing"]["iterations_run"] == 2
        assert stats["healing"]["max_iterations"] == 2


def test_e2e_agent_heals_and_recovers_on_iteration_one(app):
    """Test that self-healing recovers on first iteration and does not need 2nd iteration."""
    with app.app_context():
        project = Project(
            name="Healing Recovery App",
            target_url="https://healingrec.test",
            auth_type="none",
            crawl_depth=2,
            max_pages=5,
            target_test_count=12,
        )
        db.session.add(project)
        db.session.commit()

        run = TestRun(
            project_id=project.id,
            run_type="e2e_pipeline",
            trigger="manual",
            status="queued",
        )
        db.session.add(run)
        db.session.commit()

        agent = EndToEndAgent()
        cancel_event = MagicMock()
        cancel_event.is_set.return_value = False

        # First run: 1 failed automation issue. Second run (after healing): 0 failed.
        first_exec_result = {
            "summary": {"total": 3, "passed": 2, "failed": 1, "duration_ms": 120},
            "tests": [
                {
                    "test_name": "test_login_submit",
                    "scenario_title": "User Authentication Flow",
                    "status": "failed",
                    "error_message": "Timeout 5000ms waiting for locator('button#submit')",
                    "traceback": "TimeoutError: locator('button#submit')",
                    "failure_classification": "AUTOMATION_FAILURE",
                    "subtype": "LOCATOR_TIMEOUT",
                }
            ],
        }
        second_exec_result = {
            "summary": {"total": 3, "passed": 3, "failed": 0, "duration_ms": 110},
            "tests": [{"test_name": "test_login_submit", "status": "passed"}],
        }

        with patch("app.core.test_runner.TestRunner.execute", side_effect=[
            first_exec_result,
            second_exec_result,
        ]):
            agent.run_pipeline(
                run_id=run.id,
                cancel_event=cancel_event,
                project_id=project.id,
                crawl_depth=2,
                max_pages=5,
                target_test_count=12,
            )

        db.session.refresh(run)
        assert run.status == "completed"
        stats = run.get_summary_stats()

        # Successfully healed on iteration 1, so iterations_run == 1
        assert stats["healing"]["iterations_run"] == 1
        assert stats["healing"]["max_iterations"] == 2
        assert stats["healing"]["healed_count"] == 1
        assert stats["execution"]["passed"] == 3
        assert stats["execution"]["failed"] == 0


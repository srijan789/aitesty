import time
import pytest
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.pipeline_run import PipelineRun
from app.models.healer_attempt import HealerAttempt
from app.core.pipeline_orchestrator import PipelineOrchestrator
from config import TestingConfig


@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


def _make_project(name="Pipeline App", target_url="https://pipeline.test"):
    project = Project(name=name, target_url=target_url, auth_type="none")
    db.session.add(project)
    db.session.commit()
    return project


def _make_pipeline_run(project, max_replan_cycles=2, max_heal_attempts=3):
    pr = PipelineRun(
        project_id=project.id,
        status="running",
        max_replan_cycles=max_replan_cycles,
        max_heal_attempts=max_heal_attempts,
    )
    db.session.add(pr)
    db.session.commit()
    return pr


def _make_test_case(project, title="Some Scenario", category="edge_case"):
    plan = TestPlan(project_id=project.id, version=1, status="active", summary="test plan")
    db.session.add(plan)
    db.session.flush()
    tc = TestCase(
        test_plan_id=plan.id,
        title=title,
        category=category,
        status="automated",
        script_path="tests/test_x.spec.py",
    )
    db.session.add(tc)
    db.session.commit()
    return tc


def _wait_for_pipeline(app, run_id, timeout_iters=120):
    for _ in range(timeout_iters):
        time.sleep(0.15)
        with app.app_context():
            pr = db.session.get(PipelineRun, run_id)
            if pr.status in ("completed", "failed", "cancelled"):
                return pr.status, pr.get_final_report(), pr.replan_count
    return "timeout", {}, None


def test_full_pipeline_completes_and_produces_report(app):
    with app.app_context():
        project = _make_project()
        pipeline_run = PipelineOrchestrator.trigger_pipeline(project.id, trigger_source="test")
        run_id = pipeline_run.id

    status, report, _ = _wait_for_pipeline(app, run_id)

    assert status == "completed"
    # MockExplorerAgent always returns 2 happy_path, 1 edge_case, 2 error_flow scenarios.
    assert report["scenarios_covered"]["total"] == 5
    assert report["scenarios_covered"]["by_category"] == {"happy_path": 2, "edge_case": 1, "error_flow": 2}

    # Simulated execution: happy_path passes, edge_case fails then gets healed by the Healer's
    # script-repair path, error_flow fails and gets escalated as a classified application defect.
    summary = report["summary"]
    assert summary["passed"] == 2
    assert summary["healed"] == 1
    assert summary["escalated"] == 2
    assert summary["unresolved"] == 0
    assert summary["total"] == 5

    statuses = {r["final_status"] for r in report["pass_fail_outcomes"]}
    assert statuses == {"passed", "healed", "escalated"}

    # 1 edge_case (2 attempts to resolve) + 2 error_flow (1 escalated attempt each) = 4 rows.
    assert len(report["healer_actions_taken"]) == 4
    assert report["replan_cycles_used"] == 0


def test_replan_loop_bounded_by_max_cycles(app):
    # Threshold the mock's static plan can never satisfy -> forces re-planning every cycle.
    app.config["COVERAGE_THRESHOLD"] = 0.99

    with app.app_context():
        project = _make_project(name="Replan App", target_url="https://replan.test")
        pipeline_run = PipelineOrchestrator.trigger_pipeline(project.id, trigger_source="test")
        run_id = pipeline_run.id
        max_cycles = pipeline_run.max_replan_cycles

    status, report, replan_count = _wait_for_pipeline(app, run_id)

    assert status == "completed"  # still proceeds through the pipeline once the cap is hit
    assert replan_count == max_cycles
    assert report["replan_cycles_used"] == max_cycles


def test_healer_exhausts_attempts_and_escalates_unresolved_script_bug(app):
    with app.app_context():
        project = _make_project(name="Heal App", target_url="https://heal.test")
        pipeline_run = _make_pipeline_run(project, max_heal_attempts=3)
        tc = _make_test_case(project, title="Persistent Bug Scenario", category="edge_case")

        failing = [{
            "test_case_id": tc.id,
            "title": tc.title,
            "category": tc.category,
            "status": "failed",
            "failure_output": "TimeoutError: PERSISTENT_BUG selector never resolves",
            "script_path": tc.script_path,
        }]

        PipelineOrchestrator._run_healing_stage(project, pipeline_run, failing, lambda: False)

        attempts = HealerAttempt.query.filter_by(pipeline_run_id=pipeline_run.id).order_by(HealerAttempt.attempt_number).all()
        assert len(attempts) == pipeline_run.max_heal_attempts
        assert all(a.classification == "script_bug" for a in attempts)
        assert all(a.resolved is False for a in attempts)
        assert failing[0]["status"] == "escalated"


def test_app_defect_is_classified_and_recommended_not_fixed(app):
    # The Healer never modifies application code -- a suspected genuine defect always gets
    # classified + a recommendation surfaced for human review, escalating after one attempt.
    with app.app_context():
        project = _make_project(name="Defect App", target_url="https://defect.test")
        pipeline_run = _make_pipeline_run(project, max_heal_attempts=3)
        tc = _make_test_case(project, title="Checkout 500 Error", category="error_flow")

        failing = [{
            "test_case_id": tc.id,
            "title": tc.title,
            "category": tc.category,
            "status": "failed",
            "failure_output": "AssertionError: unexpected 500 Internal Server Error",
            "script_path": tc.script_path,
        }]

        PipelineOrchestrator._run_healing_stage(project, pipeline_run, failing, lambda: False)

        attempts = HealerAttempt.query.filter_by(pipeline_run_id=pipeline_run.id).all()
        assert len(attempts) == 1
        assert attempts[0].classification == "app_defect"
        assert attempts[0].action_taken == "recommended_fix"
        assert attempts[0].recommendation_text
        assert attempts[0].resolved is False
        assert failing[0]["status"] == "escalated"

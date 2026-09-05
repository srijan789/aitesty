import time
import pytest
from app import create_app
from app.extensions import db
from app.models.project import Project
from app.models.test_run import TestRun
from app.core.task_runner import TaskRunner
from config import TestingConfig

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

def test_task_runner_executes_and_completes(app):
    runner = TaskRunner(max_workers=2)
    runner.init_app(app)

    with app.app_context():
        proj = Project(name="Task App", target_url="https://app.test")
        db.session.add(proj)
        db.session.commit()

        run = TestRun(project_id=proj.id, run_type="exploration", status="queued")
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    def dummy_task(run_id, cancel_event):
        time.sleep(0.1)

    submitted = runner.submit_task(run_id, dummy_task)
    assert submitted is True

    # Poll until completed
    for _ in range(30):
        time.sleep(0.1)
        with app.app_context():
            r = db.session.get(TestRun, run_id)
            if r.status == "completed":
                break

    with app.app_context():
        r = db.session.get(TestRun, run_id)
        assert r.status == "completed"
        assert r.duration_ms is not None
        assert r.duration_ms >= 50
    runner.wait_for_all_tasks(timeout=2.0)
    runner.executor.shutdown(wait=True)

def test_task_runner_cancellation(app):
    runner = TaskRunner(max_workers=2)
    runner.init_app(app)

    with app.app_context():
        proj = Project(name="Cancel App", target_url="https://app.test")
        db.session.add(proj)
        db.session.commit()

        run = TestRun(project_id=proj.id, run_type="exploration", status="queued")
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    def slow_cancellable_task(run_id, cancel_event):
        for _ in range(50):
            if cancel_event.is_set():
                return
            time.sleep(0.05)

    runner.submit_task(run_id, slow_cancellable_task)
    time.sleep(0.05)
    runner.cancel_task(run_id)

    # Poll until cancelled
    for _ in range(30):
        time.sleep(0.1)
        with app.app_context():
            r = db.session.get(TestRun, run_id)
            if r.status == "cancelled":
                break

    with app.app_context():
        r = db.session.get(TestRun, run_id)
        assert r.status == "cancelled"
    runner.wait_for_all_tasks(timeout=2.0)
    runner.executor.shutdown(wait=True)

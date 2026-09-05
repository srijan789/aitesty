import logging
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Dict, Any, Optional

logger = logging.getLogger(__name__)

class TaskRunner:
    """
    Thread-pool based background task runner with Flask app context binding,
    status tracking, cancellation tokens, and database/disk log synchronization.
    """

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AitestyTask")
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.app = None

    def init_app(self, app):
        self.app = app
        max_workers = app.config.get("MAX_CONCURRENT_TASKS", 4)
        # re-initialize executor if needed
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AitestyTask")

    def submit_task(self, run_id: str, target_fn: Callable, *args, run_model=None, **kwargs) -> bool:
        """
        Submits a background task wrapped in app context and error boundaries.
        :param run_model: the SQLAlchemy model class to track status on (defaults to TestRun).
                           Pass PipelineRun when run_id identifies a PipelineRun row instead.
        """
        with self._lock:
            if run_id in self._active_tasks and self._active_tasks[run_id]["status"] == "running":
                logger.warning(f"Task for run {run_id} is already active.")
                return False

            cancel_event = threading.Event()
            self._active_tasks[run_id] = {
                "cancel_event": cancel_event,
                "status": "queued",
                "submitted_at": datetime.utcnow(),
                "future": None,
            }

        app = self.app

        def runner_wrapper():
            with self._lock:
                if run_id in self._active_tasks:
                    self._active_tasks[run_id]["status"] = "running"

            if app:
                with app.app_context():
                    self._execute_with_tracking(run_id, cancel_event, target_fn, run_model, *args, **kwargs)
            else:
                self._execute_with_tracking(run_id, cancel_event, target_fn, run_model, *args, **kwargs)

        future = self.executor.submit(runner_wrapper)
        with self._lock:
            if run_id in self._active_tasks:
                self._active_tasks[run_id]["future"] = future

        return True

    def _execute_with_tracking(self, run_id: str, cancel_event: threading.Event, fn: Callable, run_model=None, *args, **kwargs):
        from app.extensions import db
        from app.models.test_run import TestRun, RunLog

        model_cls = run_model or TestRun
        run = db.session.get(model_cls, run_id)
        if not run:
            logger.error(f"Cannot execute task: {model_cls.__name__} {run_id} not found in DB.")
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        db.session.commit()

        start_time = time.time()
        try:
            # Pass cancel_event and logger callback to target_fn
            fn(run_id=run_id, cancel_event=cancel_event, *args, **kwargs)

            # Check if cancelled during execution
            if cancel_event.is_set():
                run.status = "cancelled"
            else:
                # Reload run in case target_fn modified attributes
                db.session.refresh(run)
                if run.status != "failed":
                    run.status = "completed"

        except Exception as e:
            logger.exception(f"Error executing run {run_id}: {e}")
            tb = traceback.format_exc()
            run.status = "failed"
            run.error_message = str(e)

            # Record error in DB RunLog (per-stage TestRun runs only; PipelineRun has no
            # standalone log stream of its own -- its nested TestRun stages carry the detail)
            if model_cls is TestRun:
                err_log = RunLog(
                    run_id=run_id,
                    level="ERROR",
                    message=f"Execution failed: {str(e)}\n{tb}",
                )
                db.session.add(err_log)
        finally:
            run.completed_at = datetime.utcnow()
            run.duration_ms = int((time.time() - start_time) * 1000)
            db.session.commit()

            with self._lock:
                if run_id in self._active_tasks:
                    self._active_tasks[run_id]["status"] = run.status

    def cancel_task(self, run_id: str) -> bool:
        """Signals a task to cancel."""
        with self._lock:
            task_info = self._active_tasks.get(run_id)
            if not task_info:
                return False
            task_info["cancel_event"].set()
            task_info["status"] = "cancelling"
            return True

    def get_task_status(self, run_id: str) -> Optional[str]:
        with self._lock:
            task_info = self._active_tasks.get(run_id)
            if task_info:
                return task_info["status"]
        return None

task_runner = TaskRunner()

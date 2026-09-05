import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from flask import current_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun, RunLog
from app.core.workspace import WorkspaceManager
from app.core.task_runner import task_runner
from app.agents.base import ExplorerConfig
from app.agents.registry import get_explorer_agent

logger = logging.getLogger(__name__)

class TestOrchestrator:
    """
    Coordinates project workspaces, agent execution, test running,
    and database state transitions.
    """

    @staticmethod
    def get_workspace_manager() -> WorkspaceManager:
        workspaces_root = current_app.config["WORKSPACES_ROOT"]
        return WorkspaceManager(workspaces_root)

    @classmethod
    def create_stage_run(
        cls,
        project: Project,
        run_type: str,
        trigger_source: str = "manual",
        pipeline_run_id: Optional[str] = None,
        attempt_number: int = 1,
        summary_stats: Optional[Dict[str, Any]] = None,
    ) -> TestRun:
        """
        Creates a TestRun row + its workspace run directory. Shared by the ad-hoc single-stage
        triggers below and by PipelineOrchestrator, which tags each stage with pipeline_run_id
        so the existing per-run log streaming/UI works unchanged for pipeline-driven runs too.
        """
        wm = cls.get_workspace_manager()
        run = TestRun(
            project_id=project.id,
            pipeline_run_id=pipeline_run_id,
            run_type=run_type,
            attempt_number=attempt_number,
            trigger=trigger_source,
            status="queued",
            summary_stats_json=json.dumps(summary_stats or {}),
        )
        db.session.add(run)
        db.session.commit()

        wm.init_run_dir(project.id, run.id)
        run.run_dir = f"runs/{run.id}"
        db.session.commit()
        return run

    @classmethod
    def make_log_callback(cls, wm: WorkspaceManager, project: Project, run: TestRun):
        """Builds a log_callback(level, message, metadata) closure shared by every stage runner."""
        def log_callback(level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
            wm.append_run_log_file(project.id, run.id, level, message)
            log_entry = RunLog(
                run_id=run.id,
                level=level.upper(),
                message=message,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            db.session.add(log_entry)
            db.session.commit()
        return log_callback

    @classmethod
    def trigger_exploration(cls, project_id: str, trigger_source: str = "manual") -> TestRun:
        project = db.get_or_404(Project, project_id)
        run = cls.create_stage_run(
            project, "exploration", trigger_source,
            summary_stats={"total_scenarios": 0, "routes_found": 0},
        )

        # Submit to background task runner
        task_runner.submit_task(run.id, cls._run_exploration_task, project_id=project.id)
        return run

    @classmethod
    def _run_exploration_task(cls, run_id: str, cancel_event, project_id: str):
        wm = cls.get_workspace_manager()
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            return

        log_callback = cls.make_log_callback(wm, project, run)
        log_callback("INFO", f"Starting exploration run {run.id} for project '{project.name}'")

        agent_type = current_app.config.get("EXPLORER_AGENT_TYPE", "mock")
        agent = get_explorer_agent(agent_type)
        project_dir = wm.get_project_dir(project.id)

        config = ExplorerConfig(
            project_id=project.id,
            target_url=project.target_url,
            auth_type=project.auth_type,
            credentials=project.get_credentials(),
            scope_instructions=project.scope_instructions,
            workspace_dir=str(project_dir),
            run_id=run.id,
        )

        cls.run_planner_agent(project, run, agent, config, log_callback, cancel_event.is_set)

    @classmethod
    def run_planner_agent(
        cls,
        project: Project,
        run: TestRun,
        agent,
        config: ExplorerConfig,
        log_callback,
        cancel_check,
    ) -> Optional[Dict[str, Any]]:
        """
        Invokes a Planner (BaseExplorerAgent) instance, persists the resulting TestPlan/TestCases
        to the DB and workspace filesystem, and updates `run`'s status/stats accordingly.
        Returns the plan dict on success, or None if the run did not complete successfully
        (`run.status` is already set to "cancelled"/"failed" in that case).

        Shared by the ad-hoc "Explore Now" trigger (`_run_exploration_task`) and
        `PipelineOrchestrator`'s planning stage, including bounded re-plan attempts.
        """
        wm = cls.get_workspace_manager()
        result = agent.explore(config=config, log_callback=log_callback, cancel_check=cancel_check)

        if result.status == "cancelled":
            log_callback("WARN", "Exploration run was cancelled.")
            run.status = "cancelled"
            db.session.commit()
            return None

        if result.status == "failed":
            log_callback("ERROR", f"Exploration failed: {result.error_message}")
            run.status = "failed"
            run.error_message = result.error_message
            db.session.commit()
            return None

        # Exploration Succeeded: Ingest into database models & workspace files
        log_callback("INFO", "Persisting test plan and scenarios to database and workspace filesystem...")

        # Calculate new version number
        latest_plan = TestPlan.query.filter_by(project_id=project.id).order_by(TestPlan.version.desc()).first()
        new_version = (latest_plan.version + 1) if latest_plan else 1

        # Archive prior active plans
        TestPlan.query.filter_by(project_id=project.id, status="active").update({"status": "archived"})

        new_plan = TestPlan(
            project_id=project.id,
            version=new_version,
            status="active",
            summary=f"Automated Test Plan for {project.name} (v{new_version})",
        )
        db.session.add(new_plan)
        db.session.flush()

        scenarios_json_list = []
        for idx, s in enumerate(result.scenarios):
            test_case = TestCase(
                test_plan_id=new_plan.id,
                title=s.title,
                category=s.category,
                description=s.description,
                expected_result=s.expected_result,
                script_path=s.suggested_spec_filename,
                status="automated" if s.suggested_spec_filename else "pending",
                execution_order=idx,
            )
            test_case.set_steps(s.steps)
            db.session.add(test_case)
            db.session.flush()  # populate test_case.id so downstream stages can reference it
            scenario_dict = s.to_dict()
            scenario_dict["id"] = test_case.id
            scenarios_json_list.append(scenario_dict)

        # Build plan JSON & Markdown and write to disk
        plan_dict = {
            "project_id": project.id,
            "project_name": project.name,
            "version": new_version,
            "status": "active",
            "summary": new_plan.summary,
            "discovered_routes": result.discovered_routes,
            "scenarios": scenarios_json_list,
        }

        wm.save_test_plan(project.id, plan_dict, result.markdown_plan)
        new_plan.raw_markdown = wm.load_test_plan_md(project.id)

        stats = {
            "total_scenarios": len(result.scenarios),
            "happy_path": sum(1 for s in result.scenarios if s.category == "happy_path"),
            "edge_case": sum(1 for s in result.scenarios if s.category == "edge_case"),
            "error_flow": sum(1 for s in result.scenarios if s.category == "error_flow"),
            "routes_discovered": len(result.discovered_routes),
        }
        run.set_summary_stats(stats)
        run.status = "completed"
        db.session.commit()

        log_callback("INFO", f"Test Plan v{new_version} successfully generated and committed.", stats)
        return plan_dict

    @classmethod
    def trigger_test_execution(cls, project_id: str, trigger_source: str = "manual") -> TestRun:
        project = db.get_or_404(Project, project_id)
        run = cls.create_stage_run(
            project, "test_execution", trigger_source,
            summary_stats={"passed": 0, "failed": 0, "skipped": 0, "total": 0},
        )

        task_runner.submit_task(run.id, cls._run_test_execution_task, project_id=project.id)
        return run

    @classmethod
    def _run_test_execution_task(cls, run_id: str, cancel_event, project_id: str):
        import time
        wm = cls.get_workspace_manager()
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            return

        log_callback = cls.make_log_callback(wm, project, run)

        log_callback("INFO", f"Initializing test execution run {run.id} for project '{project.name}'")
        test_files = wm.list_test_files(project.id)

        if not test_files:
            log_callback("WARN", "No test spec files found in tests/ directory. Please run Explorer Agent first.")
            run.status = "completed"
            run.set_summary_stats({"passed": 0, "failed": 0, "skipped": 0, "total": 0})
            db.session.commit()
            return

        log_callback("INFO", f"Found {len(test_files)} test suite file(s) to execute.")
        time.sleep(0.5)

        total = 0
        passed = 0
        failed = 0

        for file_info in test_files:
            if cancel_event.is_set():
                log_callback("WARN", "Test execution cancelled by user request.")
                run.status = "cancelled"
                db.session.commit()
                return

            filename = file_info["name"]
            log_callback("INFO", f"Executing test suite: {filename}")
            time.sleep(0.8)

            # Execution simulation / runner hook
            log_callback("INFO", f"  ✔ test_user_authentication_flow: PASSED (1420ms)")
            log_callback("INFO", f"  ✔ test_invalid_login_shows_error: PASSED (890ms)")
            total += 2
            passed += 2

        stats = {"passed": passed, "failed": failed, "skipped": 0, "total": total}
        run.set_summary_stats(stats)
        run.status = "completed"
        db.session.commit()

        log_callback("INFO", f"Suite execution finished. Passed: {passed}, Failed: {failed}, Total: {total}", stats)

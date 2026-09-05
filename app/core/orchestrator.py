import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

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
    def trigger_exploration(
        cls,
        project_id: str,
        trigger_source: str = "manual",
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None,
    ) -> TestRun:
        project = db.get_or_404(Project, project_id)
        wm = cls.get_workspace_manager()

        # Create TestRun record
        run = TestRun(
            project_id=project.id,
            run_type="exploration",
            trigger=trigger_source,
            status="queued",
            summary_stats_json=json.dumps({"total_scenarios": 0, "routes_found": 0}),
        )
        db.session.add(run)
        db.session.commit()

        # Initialize filesystem artifacts directory
        run_dir = wm.init_run_dir(project.id, run.id)
        run.run_dir = f"runs/{run.id}"
        db.session.commit()

        # Submit to background task runner
        task_runner.submit_task(
            run.id,
            cls._run_exploration_task,
            project_id=project.id,
            headless=headless,
            slow_mo=slow_mo,
        )
        return run

    @classmethod
    def _run_exploration_task(
        cls,
        run_id: str,
        cancel_event,
        project_id: str,
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None,
    ):
        wm = cls.get_workspace_manager()
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            return

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

        log_callback("INFO", f"Starting exploration run {run.id} for project '{project.name}'")

        agent_type = current_app.config.get("EXPLORER_AGENT_TYPE", "mock")
        agent = get_explorer_agent(agent_type)
        project_dir = wm.get_project_dir(project.id)

        if headless is None:
            headless = current_app.config.get("PLAYWRIGHT_HEADLESS", True)
        if slow_mo is None:
            slow_mo = current_app.config.get("PLAYWRIGHT_SLOW_MO", 500 if not headless else 0)

        config = ExplorerConfig(
            project_id=project.id,
            target_url=project.target_url,
            auth_type=project.auth_type,
            credentials=project.get_credentials(),
            scope_instructions=project.scope_instructions,
            workspace_dir=str(project_dir),
            run_id=run.id,
            prd_text=project.prd_text,
            headless=headless,
            slow_mo=slow_mo,
        )

        result = agent.explore(
            config=config,
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )

        if result.status == "cancelled":
            log_callback("WARN", "Exploration run was cancelled.")
            run.status = "cancelled"
            db.session.commit()
            return

        if result.status == "failed":
            log_callback("ERROR", f"Exploration failed: {result.error_message}")
            run.status = "failed"
            run.error_message = result.error_message
            db.session.commit()
            return

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
                priority=getattr(s, "priority", "P1"),
                preconditions=getattr(s, "preconditions", None),
                description=s.description,
                expected_result=s.expected_result,
                pass_fail_criteria=getattr(s, "pass_fail_criteria", None),
                script_path=None,
                status="pending_review",
                execution_order=idx,
            )
            test_case.set_steps(s.steps)
            db.session.add(test_case)
            scenarios_json_list.append(test_case.to_dict())

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

        paths = wm.save_test_plan(project.id, plan_dict, result.markdown_plan)
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

    @classmethod
    def trigger_test_generation(
        cls,
        project_id: str,
        scenario_ids: Optional[List[str]] = None,
        trigger_source: str = "manual"
    ) -> TestRun:
        """
        Triggers the autonomous Test Creation Agent to synthesize executable
        Playwright test scripts for scenarios marked for automation.
        """
        project = db.get_or_404(Project, project_id)
        wm = cls.get_workspace_manager()

        run = TestRun(
            project_id=project.id,
            run_type="test_generation",
            trigger=trigger_source,
            status="queued",
            summary_stats_json=json.dumps({"scenarios_automated": 0, "files_created": 0}),
        )
        db.session.add(run)
        db.session.commit()

        wm.init_run_dir(project.id, run.id)
        run.run_dir = f"runs/{run.id}"
        db.session.commit()

        task_runner.submit_task(
            run.id,
            cls._run_test_generation_task,
            project_id=project.id,
            scenario_ids=scenario_ids,
        )
        return run

    @classmethod
    def _run_test_generation_task(
        cls,
        run_id: str,
        cancel_event,
        project_id: str,
        scenario_ids: Optional[List[str]] = None,
    ):
        from app.agents.base import GeneratorConfig
        from app.agents.registry import get_generator_agent

        wm = cls.get_workspace_manager()
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            return

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

        log_callback("INFO", f"Initializing Test Creation Agent run {run.id} for project '{project.name}'")

        # Find active plan
        active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first()
        if not active_plan:
            log_callback("WARN", "No active test plan found. Please run the Explorer Agent first.")
            run.status = "failed"
            run.error_message = "No active test plan found."
            db.session.commit()
            return

        # Query scenarios to automate
        scenarios_query = TestCase.query.filter_by(test_plan_id=active_plan.id)
        if scenario_ids:
            scenarios_query = scenarios_query.filter(TestCase.id.in_(scenario_ids))
        else:
            # By default, target scenarios with status 'marked_for_automation'
            marked = scenarios_query.filter_by(status="marked_for_automation").all()
            if marked:
                scenarios_to_generate = marked
            else:
                # If none explicitly marked, target all pending review / approved
                log_callback("INFO", "No scenarios specifically marked for automation. Targeting all active plan scenarios.")
                scenarios_to_generate = scenarios_query.all()

        if not scenario_ids and 'scenarios_to_generate' in locals():
            target_list = scenarios_to_generate
        else:
            target_list = scenarios_query.all()

        if not target_list:
            log_callback("WARN", "No test scenarios available for code generation.")
            run.status = "completed"
            run.set_summary_stats({"scenarios_automated": 0, "files_created": 0})
            db.session.commit()
            return

        log_callback("INFO", f"Selected {len(target_list)} scenario(s) for test creation.")

        agent_type = current_app.config.get("GENERATOR_AGENT_TYPE", "playwright")
        generator = get_generator_agent(agent_type)
        project_dir = wm.get_project_dir(project.id)

        config = GeneratorConfig(
            project_id=project.id,
            target_url=project.target_url,
            auth_type=project.auth_type,
            credentials=project.get_credentials(),
            workspace_dir=str(project_dir),
            run_id=run.id,
            scenarios=[tc.to_dict() for tc in target_list],
            scope_instructions=project.scope_instructions,
            prd_text=project.prd_text,
        )

        gen_result = generator.generate(
            config=config,
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )

        if gen_result.status == "cancelled":
            log_callback("WARN", "Test creation cancelled by user.")
            run.status = "cancelled"
            db.session.commit()
            return

        if gen_result.status == "failed":
            log_callback("ERROR", f"Test creation failed: {gen_result.error_message}")
            run.status = "failed"
            run.error_message = gen_result.error_message
            db.session.commit()
            return

        # Update testcase records in DB
        automated_ids = set(gen_result.automated_scenario_ids)
        for gen_file in gen_result.generated_files:
            file_sc_ids = gen_file.scenario_ids
            for sc_id in file_sc_ids:
                tc = db.session.get(TestCase, sc_id)
                if tc:
                    tc.status = "automated"
                    tc.script_path = gen_file.relative_path

        # If any targeted scenarios weren't mapped to specific files, mark them automated with first file
        first_rel = gen_result.generated_files[0].relative_path if gen_result.generated_files else "tests/test_suite.spec.py"
        for tc in target_list:
            if not tc.script_path:
                tc.status = "automated"
                tc.script_path = first_rel

        db.session.commit()

        # Update test_plan.json on disk
        wm.save_test_plan(project.id, active_plan.to_dict())

        total_subtests = sum(getattr(f, "subtest_count", getattr(f, "test_count", 1)) for f in gen_result.generated_files)
        stats = {
            "scenarios_automated": len(target_list),
            "files_created": len(gen_result.generated_files),
            "subtests_created": total_subtests,
            "subtests_per_test": [
                {
                    "file_name": f.filename,
                    "relative_path": f.relative_path,
                    "subtests_count": getattr(f, "subtest_count", getattr(f, "test_count", 1)),
                    "subtests_total": getattr(f, "subtest_count", getattr(f, "test_count", 1)),
                }
                for f in gen_result.generated_files
            ],
        }
        run.set_summary_stats(stats)
        run.status = "completed"
        db.session.commit()

        log_callback("INFO", f"Test Creation complete! Automated {len(target_list)} scenario(s) ({total_subtests} subtests) across {len(gen_result.generated_files)} spec file(s).", stats)

    @classmethod
    def trigger_test_execution(
        cls,
        project_id: str,
        target_file: Optional[str] = None,
        scenario_id: Optional[str] = None,
        target_files: Optional[List[str]] = None,
        target_tests: Optional[List[str]] = None,
        trigger_source: str = "manual",
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None,
    ) -> TestRun:
        """
        Triggers execution of either all test specs in the repository (suite run),
        a specific spec file / individual test, or a multi-selection of files/tests.
        """
        project = db.get_or_404(Project, project_id)
        wm = cls.get_workspace_manager()

        run = TestRun(
            project_id=project.id,
            run_type="test_execution",
            trigger=trigger_source,
            status="queued",
            summary_stats_json=json.dumps({"passed": 0, "failed": 0, "skipped": 0, "total": 0}),
        )
        db.session.add(run)
        db.session.commit()

        wm.init_run_dir(project.id, run.id)
        run.run_dir = f"runs/{run.id}"
        db.session.commit()

        task_runner.submit_task(
            run.id,
            cls._run_test_execution_task,
            project_id=project.id,
            target_file=target_file,
            scenario_id=scenario_id,
            target_files=target_files,
            target_tests=target_tests,
            headless=headless,
            slow_mo=slow_mo,
        )
        return run

    @classmethod
    def _run_test_execution_task(
        cls,
        run_id: str,
        cancel_event,
        project_id: str,
        target_file: Optional[str] = None,
        scenario_id: Optional[str] = None,
        target_files: Optional[List[str]] = None,
        target_tests: Optional[List[str]] = None,
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None,
    ):
        from app.core.test_runner import TestRunner

        wm = cls.get_workspace_manager()
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            return

        def log_callback(level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
            wm.append_run_log_file(project.id, run.id, level, message)
            test_name = metadata.get("test_name") if metadata else None
            scenario_id = metadata.get("scenario_id") if metadata else None
            if test_name:
                wm.append_test_log_file(project.id, run.id, test_name, level, message)
            log_entry = RunLog(
                run_id=run.id,
                level=level.upper(),
                message=message,
                metadata_json=json.dumps(metadata) if metadata else None,
                test_name=test_name,
                scenario_id=scenario_id,
            )
            db.session.add(log_entry)
            db.session.commit()

        log_callback("INFO", f"Initializing test execution run {run.id} for project '{project.name}'")
        project_dir = wm.get_project_dir(project.id)

        if headless is None:
            headless = current_app.config.get("PLAYWRIGHT_HEADLESS", True)
        if slow_mo is None:
            slow_mo = current_app.config.get("PLAYWRIGHT_SLOW_MO", 500 if not headless else 0)

        runner = TestRunner(
            workspace_dir=str(project_dir),
            project_id=project.id,
            run_id=run.id,
            target_url=project.target_url,
            headless=headless,
            slow_mo=slow_mo,
        )

        results = runner.execute(
            target_file=target_file,
            target_test_name=scenario_id,
            target_files=target_files,
            target_test_names=target_tests,
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )

        if cancel_event.is_set():
            run.status = "cancelled"
            db.session.commit()
            return

        summary = results.get("summary", {})
        run.set_summary_stats(summary)
        run.duration_ms = summary.get("duration_ms", 0)
        run.status = "completed" if summary.get("failed", 0) == 0 else "failed"
        db.session.commit()

        log_callback(
            "INFO",
            f"Execution finished. Passed: {summary.get('passed', 0)}, Failed: {summary.get('failed', 0)} "
            f"(Bugs: {summary.get('app_defects', 0)}, Automation: {summary.get('automation_failures', 0)})",
            summary,
        )

    @classmethod
    def trigger_healing_analysis(
        cls,
        project_id: str,
        run_ids: Optional[List[str]] = None,
        trigger_source: str = "manual",
    ) -> TestRun:
        """
        Triggers the Results Analysis & Healing Agent on selected test runs (or latest failed runs).
        """
        project = db.get_or_404(Project, project_id)
        wm = cls.get_workspace_manager()

        # If run_ids not provided, find the latest failed test execution run
        if not run_ids:
            latest_failed = (
                TestRun.query.filter_by(project_id=project.id, run_type="test_execution")
                .filter(TestRun.status.in_(["failed", "completed"]))
                .order_by(TestRun.started_at.desc())
                .first()
            )
            if latest_failed:
                run_ids = [latest_failed.id]
            else:
                run_ids = []

        run = TestRun(
            project_id=project.id,
            run_type="healing",
            trigger=trigger_source,
            status="queued",
            summary_stats_json=json.dumps({
                "target_runs": run_ids,
                "failed_cases_analyzed": 0,
                "app_defects_count": 0,
                "automation_failures_count": 0,
                "healed_tests_count": 0,
                "invalid_tests_count": 0,
            }),
        )
        db.session.add(run)
        db.session.commit()

        wm.init_run_dir(project.id, run.id)
        run.run_dir = f"runs/{run.id}"
        db.session.commit()

        task_runner.submit_task(
            run.id,
            cls._run_healing_task,
            project_id=project.id,
            target_run_ids=run_ids,
        )
        return run

    @classmethod
    def _run_healing_task(
        cls,
        run_id: str,
        cancel_event,
        project_id: str,
        target_run_ids: Optional[List[str]] = None,
    ):
        from app.agents.base import HealingConfig
        from app.agents.registry import get_healing_agent

        wm = cls.get_workspace_manager()
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            return

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

        log_callback("INFO", f"Initializing Test Results Analysis & Healing run {run.id} for project '{project.name}'")

        active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first()
        scenarios_data = [tc.to_dict() for tc in active_plan.test_cases] if active_plan else []

        # Gather run results from disk
        project_dir = wm.get_project_dir(project.id)
        run_results_list = []
        for r_id in (target_run_ids or []):
            res_file = project_dir / "runs" / r_id / "results.json"
            if res_file.exists():
                try:
                    with open(res_file, "r", encoding="utf-8") as f:
                        run_results_list.append(json.load(f))
                except Exception:
                    pass

        config = HealingConfig(
            project_id=project.id,
            target_url=project.target_url,
            workspace_dir=str(project_dir),
            run_ids=target_run_ids or [],
            scenarios=scenarios_data,
            run_results=run_results_list,
            prd_text=project.prd_text,
            scope_instructions=project.scope_instructions,
        )

        agent_type = current_app.config.get("HEALER_AGENT_TYPE", "playwright")
        healer = get_healing_agent(agent_type)

        healing_result = healer.analyze_and_heal(
            config=config,
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )

        if cancel_event.is_set():
            run.status = "cancelled"
            db.session.commit()
            return

        if healing_result.status == "failed":
            run.status = "failed"
            run.error_message = healing_result.error_message
            db.session.commit()
            return

        stats = {
            "target_runs": target_run_ids or [],
            "failed_cases_analyzed": healing_result.failed_cases_analyzed,
            "app_defects_count": healing_result.app_defects_count,
            "automation_failures_count": healing_result.automation_failures_count,
            "healed_tests_count": healing_result.healed_tests_count,
            "invalid_tests_count": healing_result.invalid_tests_count,
            "analyses": [a.to_dict() for a in healing_result.analyses],
        }
        run.set_summary_stats(stats)
        run.status = "completed"
        db.session.commit()

        log_callback(
            "INFO",
            f"Healing Run Completed! Analyzed {healing_result.failed_cases_analyzed} failure(s): "
            f"{healing_result.app_defects_count} App Defects, {healing_result.automation_failures_count} Automation Issues "
            f"({healing_result.healed_tests_count} Healed, {healing_result.invalid_tests_count} Invalid).",
            stats,
        )


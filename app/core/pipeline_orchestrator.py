import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from flask import current_app
from app.extensions import db
from app.models.project import Project
from app.models.pipeline_run import PipelineRun
from app.models.test_plan import TestCase
from app.models.test_run import TestRun
from app.models.healer_attempt import HealerAttempt
from app.core.workspace import WorkspaceManager
from app.core.task_runner import task_runner
from app.core.orchestrator import TestOrchestrator
from app.core.coverage_evaluator import CoverageEvaluator, CoverageReport
from app.agents.base import ExplorerConfig, GeneratorConfig, HealerConfig
from app.agents.registry import get_explorer_agent, get_generator_agent, get_healer_agent

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    The meta-agent. Coordinates the full autonomous pipeline for one project:

        Plan -> Evaluate coverage -> (bounded re-plan loop) -> Generate -> Execute
             -> Heal failures (bounded retries per test) -> Synthesize final report

    Each stage still runs through the existing TestRun/RunLog machinery (via
    TestOrchestrator.create_stage_run / make_log_callback), tagged with this pipeline's id, so
    the existing per-run log streaming and UI keep working unchanged for pipeline-driven stages.
    """

    @staticmethod
    def get_workspace_manager() -> WorkspaceManager:
        return WorkspaceManager(current_app.config["WORKSPACES_ROOT"])

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    @classmethod
    def trigger_pipeline(
        cls,
        project_id: str,
        trigger_source: str = "manual",
        product_requirements: Optional[str] = None,
        natural_language_intent: Optional[str] = None,
    ) -> PipelineRun:
        project = db.get_or_404(Project, project_id)

        pipeline_run = PipelineRun(
            project_id=project.id,
            status="queued",
            current_stage="planning",
            trigger=trigger_source,
            max_replan_cycles=current_app.config.get("MAX_REPLAN_CYCLES", 2),
            max_heal_attempts=current_app.config.get("MAX_HEAL_ATTEMPTS", 3),
            product_requirements=product_requirements,
            natural_language_intent=natural_language_intent,
        )
        db.session.add(pipeline_run)
        db.session.commit()

        task_runner.submit_task(
            pipeline_run.id,
            cls._run_pipeline_task,
            project_id=project.id,
            run_model=PipelineRun,
        )
        return pipeline_run

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    @classmethod
    def _run_pipeline_task(cls, run_id: str, cancel_event, project_id: str):
        pipeline_run = db.session.get(PipelineRun, run_id)
        project = db.session.get(Project, project_id)
        if not pipeline_run or not project:
            return
        cancel_check = cancel_event.is_set

        # ---- 1 & 2: PLAN + EVALUATE (bounded re-plan loop) ----
        pipeline_run.current_stage = "planning"
        db.session.commit()

        attempt_number = 1
        coverage_feedback: List[str] = []
        plan_dict: Optional[Dict[str, Any]] = None
        coverage_report = CoverageReport(score=0.0)
        threshold = current_app.config.get("COVERAGE_THRESHOLD", 0.6)

        while True:
            if cancel_check():
                return

            plan_run, plan_dict, discovered_routes = cls._run_planning_stage(
                project, pipeline_run, attempt_number, coverage_feedback, cancel_check,
            )
            if cancel_check():
                return
            if plan_run.status != "completed":
                cls._mark_failed(pipeline_run, f"Planning stage ended with status '{plan_run.status}'")
                return

            pipeline_run.current_stage = "coverage_check"
            db.session.commit()

            coverage_report = CoverageEvaluator().evaluate(
                plan_dict, discovered_routes, pipeline_run.product_requirements,
            )

            if coverage_report.score >= threshold or pipeline_run.replan_count >= pipeline_run.max_replan_cycles:
                break

            pipeline_run.replan_count += 1
            db.session.commit()
            coverage_feedback = coverage_report.gaps
            attempt_number += 1
            # loop back and re-invoke the Planner with the gap feedback

        # ---- 3: GENERATE ----
        pipeline_run.current_stage = "generation"
        db.session.commit()
        gen_run = cls._run_generation_stage(project, pipeline_run, plan_dict, cancel_check)
        if cancel_check():
            return
        if gen_run.status != "completed":
            cls._mark_failed(pipeline_run, f"Generation stage ended with status '{gen_run.status}'")
            return

        # ---- 4: EXECUTE ----
        pipeline_run.current_stage = "execution"
        db.session.commit()
        exec_run, results = cls._run_execution_stage(project, pipeline_run, plan_dict, cancel_check)
        if cancel_check():
            return
        if exec_run.status != "completed":
            cls._mark_failed(pipeline_run, f"Execution stage ended with status '{exec_run.status}'")
            return

        # ---- 5: HEAL ----
        failing = [r for r in results if r["status"] == "failed"]
        if failing:
            pipeline_run.current_stage = "healing"
            db.session.commit()
            cls._run_healing_stage(project, pipeline_run, failing, cancel_check)
            if cancel_check():
                return

        # ---- 6: REPORT ----
        pipeline_run.current_stage = "reporting"
        db.session.commit()
        report = cls._synthesize_report(project, pipeline_run, plan_dict, coverage_report, results)
        pipeline_run.set_final_report(report)
        pipeline_run.current_stage = "done"
        db.session.commit()

    # ------------------------------------------------------------------
    # Stage 1: Planning
    # ------------------------------------------------------------------

    @classmethod
    def _run_planning_stage(
        cls,
        project: Project,
        pipeline_run: PipelineRun,
        attempt_number: int,
        coverage_feedback: List[str],
        cancel_check,
    ) -> Tuple[TestRun, Optional[Dict[str, Any]], List[str]]:
        run = TestOrchestrator.create_stage_run(
            project, "exploration", trigger_source="pipeline",
            pipeline_run_id=pipeline_run.id, attempt_number=attempt_number,
            summary_stats={"total_scenarios": 0, "routes_found": 0},
        )
        wm = cls.get_workspace_manager()
        log_callback = TestOrchestrator.make_log_callback(wm, project, run)

        if attempt_number > 1:
            log_callback(
                "INFO",
                f"Re-invoking Planner (attempt {attempt_number}/{pipeline_run.max_replan_cycles + 1}) "
                f"with coverage feedback: {coverage_feedback}",
            )
        else:
            log_callback("INFO", f"Pipeline planning stage starting for '{project.name}'.")

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
            product_requirements=pipeline_run.product_requirements,
            coverage_feedback=coverage_feedback,
            attempt_number=attempt_number,
        )

        plan_dict = TestOrchestrator.run_planner_agent(project, run, agent, config, log_callback, cancel_check)
        discovered_routes = plan_dict.get("discovered_routes", []) if plan_dict else []
        return run, plan_dict, discovered_routes

    # ------------------------------------------------------------------
    # Stage 2: Generation
    # ------------------------------------------------------------------

    @classmethod
    def _run_generation_stage(
        cls, project: Project, pipeline_run: PipelineRun, plan_dict: Dict[str, Any], cancel_check,
    ) -> TestRun:
        run = TestOrchestrator.create_stage_run(
            project, "generation", trigger_source="pipeline", pipeline_run_id=pipeline_run.id,
        )
        wm = cls.get_workspace_manager()
        log_callback = TestOrchestrator.make_log_callback(wm, project, run)
        log_callback("INFO", "Generator agent starting: converting the test plan into executable test files.")

        agent_type = current_app.config.get("GENERATOR_AGENT_TYPE", "mock")
        agent = get_generator_agent(agent_type)
        project_dir = wm.get_project_dir(project.id)

        config = GeneratorConfig(
            project_id=project.id,
            target_url=project.target_url,
            auth_type=project.auth_type,
            credentials=project.get_credentials(),
            workspace_dir=str(project_dir),
            run_id=run.id,
            plan=plan_dict,
        )
        result = agent.generate(config=config, log_callback=log_callback, cancel_check=cancel_check)

        if result.status != "success":
            log_callback("ERROR", f"Generation failed: {result.error_message}")
            run.status = "failed"
            run.error_message = result.error_message
            db.session.commit()
            return run

        # Persist files through WorkspaceManager (centralized path sanitization) and link
        # each generated file back to the TestCase rows / plan scenarios it covers.
        written_paths = []
        scenarios_by_id = {s.get("id"): s for s in plan_dict.get("scenarios", []) if s.get("id")}

        for f in result.files:
            wm.save_test_file(project.id, f.relative_path, f.content)
            written_paths.append(f.relative_path)
            for test_case_id in f.covers_test_case_ids:
                test_case = db.session.get(TestCase, test_case_id)
                if test_case:
                    test_case.script_path = f.relative_path
                    test_case.status = "automated"
                if test_case_id in scenarios_by_id:
                    scenarios_by_id[test_case_id]["script_path"] = f.relative_path

        db.session.commit()

        issue_count = sum(len(v.get("issues", [])) for v in result.validation_report.values() if isinstance(v, dict))
        run.set_summary_stats({"files_generated": len(written_paths), "validation_issues": issue_count})
        run.status = "completed"
        db.session.commit()

        log_callback("INFO", f"Generation complete. {len(written_paths)} file(s) written.", {"files": written_paths})
        return run

    # ------------------------------------------------------------------
    # Stage 3: Execution
    # ------------------------------------------------------------------

    @classmethod
    def _run_execution_stage(
        cls, project: Project, pipeline_run: PipelineRun, plan_dict: Dict[str, Any], cancel_check,
    ) -> Tuple[TestRun, List[Dict[str, Any]]]:
        """
        NOTE: this still simulates execution outcomes rather than actually running the generated
        Playwright specs (see the plan's "known gap" -- a real pytest/Playwright runner is a
        follow-up, drop-in replacement for this method's body). Outcomes are deterministic per
        scenario category so the Healer stage has real, reproducible failures to work with:
        edge cases fail with a stale-selector style error (a script bug the Healer can repair),
        error-flow scenarios fail with an application-error style assertion (a suspected defect).
        """
        run = TestOrchestrator.create_stage_run(
            project, "test_execution", trigger_source="pipeline", pipeline_run_id=pipeline_run.id,
            summary_stats={"passed": 0, "failed": 0, "skipped": 0, "total": 0},
        )
        wm = cls.get_workspace_manager()
        log_callback = TestOrchestrator.make_log_callback(wm, project, run)

        scenarios = plan_dict.get("scenarios", [])
        log_callback("INFO", f"Executing generated test suite ({len(scenarios)} scenario(s)).")

        results: List[Dict[str, Any]] = []
        for scenario in scenarios:
            if cancel_check():
                run.status = "cancelled"
                db.session.commit()
                return run, results

            title = scenario.get("title", "scenario")
            category = scenario.get("category", "happy_path")
            test_case_id = scenario.get("id")
            script_path = scenario.get("script_path")
            time.sleep(0.1)

            if category == "edge_case":
                status_, failure_output = "failed", f"TimeoutError: selector not found while exercising boundary input for '{title}'"
            elif category == "error_flow":
                status_, failure_output = "failed", f"AssertionError: unexpected 500 Internal Server Error while validating '{title}'"
            else:
                status_, failure_output = "passed", None

            log_callback("INFO", f"  {'✔' if status_ == 'passed' else '✘'} {title}: {status_.upper()}")
            results.append({
                "test_case_id": test_case_id,
                "title": title,
                "category": category,
                "status": status_,
                "failure_output": failure_output,
                "script_path": script_path,
            })

        passed = sum(1 for r in results if r["status"] == "passed")
        failed = sum(1 for r in results if r["status"] == "failed")
        run.set_summary_stats({"passed": passed, "failed": failed, "skipped": 0, "total": len(results)})
        run.status = "completed"
        db.session.commit()

        log_callback("INFO", f"Execution finished. Passed: {passed}, Failed: {failed}, Total: {len(results)}")
        return run, results

    # ------------------------------------------------------------------
    # Stage 4: Healing
    # ------------------------------------------------------------------

    @classmethod
    def _run_healing_stage(
        cls, project: Project, pipeline_run: PipelineRun, failing_results: List[Dict[str, Any]], cancel_check,
    ) -> TestRun:
        run = TestOrchestrator.create_stage_run(
            project, "healing", trigger_source="pipeline", pipeline_run_id=pipeline_run.id,
        )
        wm = cls.get_workspace_manager()
        log_callback = TestOrchestrator.make_log_callback(wm, project, run)
        log_callback("INFO", f"Healer stage starting for {len(failing_results)} failing test(s).")

        agent_type = current_app.config.get("HEALER_AGENT_TYPE", "mock")
        agent = get_healer_agent(agent_type)
        project_dir = wm.get_project_dir(project.id)
        max_attempts = pipeline_run.max_heal_attempts

        for failure in failing_results:
            if cancel_check():
                break

            test_case_id = failure["test_case_id"]
            script_path = failure["script_path"]
            failure_output = failure["failure_output"]
            resolved = False

            for attempt_number in range(1, max_attempts + 1):
                if cancel_check():
                    break

                config = HealerConfig(
                    project_id=project.id,
                    workspace_dir=str(project_dir),
                    run_id=run.id,
                    test_case_id=test_case_id,
                    script_path=script_path,
                    failure_output=failure_output,
                    attempt_number=attempt_number,
                    max_attempts=max_attempts,
                )
                result = agent.heal(config=config, log_callback=log_callback, cancel_check=cancel_check)

                if test_case_id:
                    db.session.add(HealerAttempt(
                        pipeline_run_id=pipeline_run.id,
                        test_case_id=test_case_id,
                        attempt_number=attempt_number,
                        classification=result.classification,
                        action_taken=result.action_taken,
                        recommendation_text=result.recommendation_text,
                        confidence=result.confidence,
                        resolved=(result.status == "resolved"),
                    ))
                    db.session.commit()

                if result.action_taken == "repaired_script" and result.updated_script_content and script_path:
                    wm.save_test_file(project.id, script_path, result.updated_script_content)

                if result.status == "resolved":
                    failure["status"] = "healed"
                    resolved = True
                    log_callback("INFO", f"Test case {test_case_id} resolved by Healer after attempt {attempt_number}.")
                    break

                if result.classification == "app_defect":
                    # A genuine application defect isn't something the Healer can fix by
                    # rewriting the test script -- nothing left to retry, just escalate.
                    log_callback(
                        "WARN",
                        f"Test case {test_case_id} escalated as a likely application defect "
                        f"(classified, not a broken locator/workflow -- a fix was recommended for review).",
                    )
                    break

                if result.status == "escalated":
                    break
                # otherwise: script_bug still unresolved -- loop to the next attempt

            if not resolved and failure.get("status") != "healed":
                failure["status"] = "escalated"

        run.status = "completed"
        db.session.commit()
        log_callback("INFO", "Healer stage complete.")
        return run

    # ------------------------------------------------------------------
    # Stage 5: Report synthesis
    # ------------------------------------------------------------------

    @classmethod
    def _synthesize_report(
        cls,
        project: Project,
        pipeline_run: PipelineRun,
        plan_dict: Dict[str, Any],
        coverage_report: CoverageReport,
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        scenarios = plan_dict.get("scenarios", [])
        by_category: Dict[str, int] = {}
        for s in scenarios:
            by_category[s.get("category", "unknown")] = by_category.get(s.get("category", "unknown"), 0) + 1

        healer_attempts = [
            ha.to_dict() for ha in
            HealerAttempt.query.filter_by(pipeline_run_id=pipeline_run.id).order_by(HealerAttempt.created_at).all()
        ]

        passed = sum(1 for r in results if r["status"] == "passed")
        healed = sum(1 for r in results if r["status"] == "healed")
        escalated = sum(1 for r in results if r["status"] == "escalated")
        unresolved = sum(1 for r in results if r["status"] == "failed")

        report = {
            "project_id": project.id,
            "project_name": project.name,
            "pipeline_run_id": pipeline_run.id,
            "generated_at": datetime.utcnow().isoformat(),
            "scenarios_covered": {"total": len(scenarios), "by_category": by_category},
            "pass_fail_outcomes": [
                {
                    "test_case_id": r["test_case_id"],
                    "title": r["title"],
                    "category": r["category"],
                    "final_status": r["status"],
                }
                for r in results
            ],
            "summary": {
                "passed": passed,
                "healed": healed,
                "escalated": escalated,
                "unresolved": unresolved,
                "total": len(results),
            },
            "healer_actions_taken": healer_attempts,
            "coverage_gaps_remaining": coverage_report.gaps,
            "untested_flow_risk": coverage_report.uncovered_routes,
            "replan_cycles_used": pipeline_run.replan_count,
            "max_replan_cycles": pipeline_run.max_replan_cycles,
        }

        lines = [
            f"# Pipeline Test Quality Report: {project.name}",
            f"\nGenerated: {report['generated_at']}",
            "\n## Summary",
            f"- Scenarios covered: {len(scenarios)} ({', '.join(f'{k}: {v}' for k, v in by_category.items())})",
            f"- Passed: {passed} | Healed: {healed} | Escalated: {escalated} | Unresolved: {unresolved}",
            f"- Re-plan cycles used: {pipeline_run.replan_count}/{pipeline_run.max_replan_cycles}",
            "\n## Coverage Gaps Remaining",
        ]
        lines += [f"- {g}" for g in coverage_report.gaps] if coverage_report.gaps else ["- None"]
        lines.append("\n## Untested Flow Risk")
        lines += [f"- {r}" for r in coverage_report.uncovered_routes] if coverage_report.uncovered_routes else ["- None"]
        lines.append("\n## Healer Actions Taken")
        if healer_attempts:
            for ha in healer_attempts:
                lines.append(
                    f"- [{ha['test_case_title']}] attempt {ha['attempt_number']}: "
                    f"{ha['classification']} -> {ha['action_taken']} (resolved={ha['resolved']})"
                )
        else:
            lines.append("- None")

        wm = cls.get_workspace_manager()
        wm.save_pipeline_report(project.id, report, "\n".join(lines))
        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mark_failed(pipeline_run: PipelineRun, message: str):
        logger.error(f"PipelineRun {pipeline_run.id} failed: {message}")
        pipeline_run.status = "failed"
        pipeline_run.error_message = message
        db.session.commit()

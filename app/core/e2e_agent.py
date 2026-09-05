import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from flask import current_app
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun, RunLog
from app.core.workspace import WorkspaceManager
from app.agents.base import (
    ExplorerConfig,
    GeneratorConfig,
    HealingConfig,
    DiscoveredScenario,
)
from app.agents.registry import (
    get_explorer_agent,
    get_generator_agent,
    get_healing_agent,
)
from app.core.coverage_critic import CoverageCritic
from app.core.test_runner import TestRunner

logger = logging.getLogger(__name__)


class TestPlanReviewer:
    """
    Autonomous Test Plan Reviewer.
    Inspects discovered test scenarios, verifies completeness, ensures criteria
    and steps are well-formed, prunes duplicates, and approves scenarios for code generation.
    """

    @classmethod
    def review_and_approve(
        cls,
        project_id: str,
        plan_id: str,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
    ) -> Dict[str, Any]:
        wm = WorkspaceManager(current_app.config["WORKSPACES_ROOT"])
        plan = db.session.get(TestPlan, plan_id)
        if not plan:
            return {"total_reviewed": 0, "approved": 0, "rejected": 0, "approved_ids": []}

        test_cases = TestCase.query.filter_by(test_plan_id=plan.id).all()
        log_callback("INFO", f"[Plan Reviewer] Reviewing {len(test_cases)} discovered test scenarios for quality, assertions, and coverage...")

        approved_ids: List[str] = []
        rejected_ids: List[str] = []
        seen_titles = set()

        category_counts = {"happy_path": 0, "edge_case": 0, "error_flow": 0}

        for tc in test_cases:
            steps = tc.get_steps() or []
            title_norm = (tc.title or "").strip().lower()

            # Quality checks
            is_valid = True
            rejection_reasons = []

            if not title_norm:
                is_valid = False
                rejection_reasons.append("Empty title")

            if title_norm in seen_titles:
                is_valid = False
                rejection_reasons.append("Duplicate scenario")
            seen_titles.add(title_norm)

            if len(steps) == 0:
                is_valid = False
                rejection_reasons.append("No action steps defined")

            if not tc.expected_result or len(tc.expected_result.strip()) < 5:
                is_valid = False
                rejection_reasons.append("Missing or incomplete expected result")

            # Enrich pass_fail_criteria if missing
            if not tc.pass_fail_criteria:
                tc.pass_fail_criteria = (
                    f"PASS: {tc.expected_result}\n"
                    f"FAIL: UI assertion failure, uncaught JS exception, or unexpected server error."
                )

            if is_valid:
                tc.status = "marked_for_automation"
                approved_ids.append(tc.id)
                cat = tc.category if tc.category in category_counts else "happy_path"
                category_counts[cat] += 1
            else:
                tc.status = "rejected"
                rejected_ids.append(tc.id)
                log_callback("WARN", f"[Plan Reviewer] Scenario '{tc.title}' rejected: {', '.join(rejection_reasons)}")

        db.session.commit()

        # Update disk files (test_plan.json & test_plan.md)
        plan_dict = plan.to_dict()
        wm.save_test_plan(project_id, plan_dict)

        review_summary = {
            "total_reviewed": len(test_cases),
            "approved": len(approved_ids),
            "rejected": len(rejected_ids),
            "approved_ids": approved_ids,
            "category_distribution": category_counts,
        }

        log_callback(
            "INFO",
            f"[Plan Reviewer] Review completed: {len(approved_ids)}/{len(test_cases)} approved for automation "
            f"({category_counts['happy_path']} happy path, {category_counts['edge_case']} edge cases, {category_counts['error_flow']} error flows).",
            review_summary,
        )
        return review_summary


class EndToEndAgent:
    """
    Autonomous End-to-End QA Pipeline Agent.
    Orchestrates the complete testing lifecycle:
      1. Deep Crawl & Route Discovery (Frontier BFS + Scenario Synthesis)
      2. Autonomous Test Plan Review & Approval
      3. Playwright Code Generation
      4. Test Suite Execution & Telemetry Collection
      5. Autonomous Self-Healing Loop (Max 2 iterations)
    """

    def __init__(self, workspace_manager: Optional[WorkspaceManager] = None):
        self.wm = workspace_manager or WorkspaceManager(current_app.config["WORKSPACES_ROOT"])

    def run_pipeline(
        self,
        run_id: str,
        cancel_event,
        project_id: str,
        crawl_depth: Optional[int] = None,
        max_pages: Optional[int] = None,
        target_test_count: Optional[int] = None,
        exploration_strategy: Optional[str] = None,
        headless: Optional[bool] = None,
        slow_mo: Optional[int] = None,
    ):
        wm = self.wm
        project = db.session.get(Project, project_id)
        run = db.session.get(TestRun, run_id)

        if not project or not run:
            logger.error(f"[E2E Agent] Project {project_id} or Run {run_id} not found.")
            return

        proj_id = project.id
        proj_name = project.name
        proj_url = project.target_url
        proj_auth_type = project.auth_type
        proj_credentials = project.get_credentials()
        proj_scope = project.scope_instructions or ""
        proj_prd = project.prd_text
        proj_crawl_depth = project.crawl_depth or 2
        proj_max_pages = project.max_pages or 10
        proj_target_tests = project.target_test_count or 12
        proj_strategy = project.exploration_strategy or "balanced"

        eff_crawl_depth = crawl_depth if crawl_depth is not None else proj_crawl_depth
        eff_max_pages = max_pages if max_pages is not None else proj_max_pages
        eff_target_tests = target_test_count if target_test_count is not None else proj_target_tests
        eff_strategy = exploration_strategy if exploration_strategy else proj_strategy

        if headless is None:
            headless = current_app.config.get("PLAYWRIGHT_HEADLESS", True)
        if slow_mo is None:
            slow_mo = current_app.config.get("PLAYWRIGHT_SLOW_MO", 500 if not headless else 0)

        pipeline_stats: Dict[str, Any] = {
            "stage": "starting",
            "progress_percent": 5,
            "crawl_depth": eff_crawl_depth,
            "max_pages": eff_max_pages,
            "target_test_count": eff_target_tests,
            "exploration": {},
            "review": {},
            "generation": {},
            "execution": {},
            "healing": {
                "iterations_run": 0,
                "max_iterations": 2,
                "app_defects_count": 0,
                "automation_failures_count": 0,
                "healed_count": 0,
            },
        }

        def log_callback(level: str, message: str, metadata: Optional[Dict[str, Any]] = None):
            wm.append_run_log_file(proj_id, run_id, level, message)
            log_entry = RunLog(
                run_id=run_id,
                level=level.upper(),
                message=message,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            db.session.add(log_entry)
            db.session.commit()

        def update_stage(stage_name: str, progress: int, extra_stats: Optional[Dict[str, Any]] = None):
            pipeline_stats["stage"] = stage_name
            pipeline_stats["progress_percent"] = progress
            if extra_stats:
                pipeline_stats.update(extra_stats)
            current_run = db.session.get(TestRun, run_id)
            if current_run:
                current_run.set_summary_stats(pipeline_stats)
                db.session.commit()

        run.status = "running"
        run.started_at = datetime.utcnow()
        update_stage("crawling", 10)

        log_callback("INFO", f"🚀 Launching Autonomous End-to-End QA Pipeline for '{proj_name}' ({proj_url})")
        log_callback("INFO", f"[Pipeline Config] Depth: {eff_crawl_depth}, Max Pages: {eff_max_pages}, Target Tests: {eff_target_tests}, Strategy: {eff_strategy}")

        project_dir = wm.get_project_dir(proj_id)

        # =====================================================================
        # STAGE 1: Deep Crawl & Exploration
        # =====================================================================
        log_callback("INFO", "═══ STAGE 1/5: Autonomous Exploration & Deep Frontier Crawl ═══")
        agent_type = current_app.config.get("EXPLORER_AGENT_TYPE", "playwright")
        explorer = get_explorer_agent(agent_type)

        explorer_cfg = ExplorerConfig(
            project_id=proj_id,
            target_url=proj_url,
            auth_type=proj_auth_type,
            credentials=proj_credentials,
            scope_instructions=proj_scope,
            workspace_dir=str(project_dir),
            run_id=run_id,
            prd_text=proj_prd,
            headless=headless,
            slow_mo=slow_mo,
            crawl_depth=eff_crawl_depth,
            max_pages=eff_max_pages,
            target_test_count=eff_target_tests,
            exploration_strategy=eff_strategy,
        )

        explore_res = explorer.explore(
            config=explorer_cfg,
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )

        if cancel_event.is_set():
            run.status = "cancelled"
            db.session.commit()
            return

        if explore_res.status == "failed":
            run.status = "failed"
            run.error_message = explore_res.error_message or "Exploration stage failed."
            db.session.commit()
            return

        # Persist discovered scenarios to TestPlan in database & disk
        latest_plan = TestPlan.query.filter_by(project_id=proj_id).order_by(TestPlan.version.desc()).first()
        new_version = (latest_plan.version + 1) if latest_plan else 1
        TestPlan.query.filter_by(project_id=proj_id, status="active").update({"status": "archived"})

        active_plan = TestPlan(
            project_id=proj_id,
            version=new_version,
            status="active",
            summary=f"E2E Automated Test Plan for {proj_name} (v{new_version})",
        )
        db.session.add(active_plan)
        db.session.flush()

        scenarios_json = []
        for idx, s in enumerate(explore_res.scenarios):
            tc = TestCase(
                test_plan_id=active_plan.id,
                title=s.title,
                category=s.category,
                priority=getattr(s, "priority", "P1"),
                preconditions=getattr(s, "preconditions", None),
                description=s.description,
                expected_result=s.expected_result,
                pass_fail_criteria=getattr(s, "pass_fail_criteria", None),
                status="pending_review",
                execution_order=idx,
            )
            tc.set_steps(s.steps)
            db.session.add(tc)
            scenarios_json.append(tc.to_dict())

        plan_dict = {
            "project_id": proj_id,
            "project_name": proj_name,
            "version": new_version,
            "status": "active",
            "summary": active_plan.summary,
            "discovered_routes": explore_res.discovered_routes,
            "scenarios": scenarios_json,
        }
        wm.save_test_plan(proj_id, plan_dict, explore_res.markdown_plan)
        db.session.commit()

        pipeline_stats["exploration"] = {
            "total_scenarios": len(explore_res.scenarios),
            "discovered_routes": len(explore_res.discovered_routes),
            "happy_path": sum(1 for s in explore_res.scenarios if s.category == "happy_path"),
            "edge_case": sum(1 for s in explore_res.scenarios if s.category == "edge_case"),
            "error_flow": sum(1 for s in explore_res.scenarios if s.category == "error_flow"),
        }
        update_stage("reviewing", 30)

        # =====================================================================
        # STAGE 2: Autonomous Test Plan Review
        # =====================================================================
        log_callback("INFO", "═══ STAGE 2/5: Autonomous Test Plan Review & Quality Gate ═══")
        review_summary = TestPlanReviewer.review_and_approve(proj_id, active_plan.id, log_callback)
        pipeline_stats["review"] = review_summary

        if cancel_event.is_set():
            run.status = "cancelled"
            db.session.commit()
            return

        if review_summary["approved"] == 0:
            log_callback("ERROR", "[E2E Agent] No test scenarios were approved during plan review.")
            run.status = "failed"
            run.error_message = "No test scenarios met quality standards during review."
            db.session.commit()
            return

        update_stage("generating", 50)

        # =====================================================================
        # STAGE 3: Test Code Generation
        # =====================================================================
        log_callback("INFO", "═══ STAGE 3/5: Playwright Test Code Generation ═══")
        approved_tcs = TestCase.query.filter_by(test_plan_id=active_plan.id, status="marked_for_automation").all()
        target_scenarios_data = [tc.to_dict() for tc in approved_tcs]

        generator_type = current_app.config.get("GENERATOR_AGENT_TYPE", "playwright")
        generator = get_generator_agent(generator_type)

        gen_config = GeneratorConfig(
            project_id=proj_id,
            target_url=proj_url,
            auth_type=proj_auth_type,
            credentials=proj_credentials,
            scope_instructions=proj_scope,
            workspace_dir=str(project_dir),
            run_id=run_id,
            scenarios=target_scenarios_data,
            prd_text=proj_prd,
        )

        gen_result = generator.generate(
            config=gen_config,
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )

        if cancel_event.is_set():
            run.status = "cancelled"
            db.session.commit()
            return

        if gen_result.status == "failed":
            run.status = "failed"
            run.error_message = gen_result.error_message or "Code generation failed."
            db.session.commit()
            return

        # Map generated files to TestCase models
        for gen_file in gen_result.generated_files:
            for sc_id in gen_file.scenario_ids:
                tc = db.session.get(TestCase, sc_id)
                if tc:
                    tc.status = "automated"
                    tc.script_path = gen_file.relative_path

        first_rel = gen_result.generated_files[0].relative_path if gen_result.generated_files else "tests/test_suite.spec.py"
        for tc in approved_tcs:
            if not tc.script_path:
                tc.status = "automated"
                tc.script_path = first_rel

        db.session.commit()
        wm.save_test_plan(proj_id, active_plan.to_dict())

        total_subtests = sum(getattr(f, "subtest_count", getattr(f, "test_count", 1)) for f in gen_result.generated_files)
        pipeline_stats["generation"] = {
            "scenarios_automated": len(approved_tcs),
            "files_created": len(gen_result.generated_files),
            "subtests_created": total_subtests,
        }
        update_stage("executing", 70)

        # =====================================================================
        # STAGE 4: Test Suite Execution
        # =====================================================================
        log_callback("INFO", "═══ STAGE 4/5: Test Suite Execution & Telemetry Collection ═══")
        runner = TestRunner(
            workspace_dir=str(project_dir),
            project_id=proj_id,
            run_id=run_id,
            target_url=proj_url,
            headless=headless,
            slow_mo=slow_mo,
        )

        exec_results = runner.execute(
            log_callback=log_callback,
            cancel_check=cancel_event.is_set,
        )
        try:
            wm.save_run_results(proj_id, run_id, exec_results)
        except Exception as e:
            logger.warning(f"Could not save run results: {e}")

        if cancel_event.is_set():
            run.status = "cancelled"
            db.session.commit()
            return

        summary = exec_results.get("summary", {})
        total_tests = summary.get("total", 0)
        passed_tests = summary.get("passed", 0)
        failed_tests = summary.get("failed", 0)

        pipeline_stats["execution"] = {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "duration_ms": summary.get("duration_ms", 0),
        }
        update_stage("healing", 85)

        # =====================================================================
        # STAGE 5: Autonomous Self-Healing Loop (Max 2 iterations)
        # =====================================================================
        log_callback("INFO", "═══ STAGE 5/5: Autonomous Self-Healing Quality Gate (Max 2 Iterations) ═══")

        heal_iteration = 0
        max_heal_loops = 2
        healer_type = current_app.config.get("HEALER_AGENT_TYPE", "playwright")
        healer = get_healing_agent(healer_type)

        remaining_failures = failed_tests
        total_healed = 0
        total_app_defects = 0
        total_auto_failures = 0

        if remaining_failures == 0:
            log_callback("INFO", "🎉 All tests passed cleanly on initial execution! Self-healing not needed.")
        else:
            log_callback("WARN", f"Detected {remaining_failures} failed test(s). Commencing autonomous self-healing loop...")

            while remaining_failures > 0 and heal_iteration < max_heal_loops:
                heal_iteration += 1
                if cancel_event.is_set():
                    run.status = "cancelled"
                    db.session.commit()
                    return

                log_callback("INFO", f"─── Self-Healing Loop Iteration {heal_iteration}/{max_heal_loops} ───")

                # 1. Run Healer Analysis
                results_file = project_dir / "runs" / run_id / "results.json"
                run_results_data = []
                if results_file.exists():
                    try:
                        with open(results_file, "r", encoding="utf-8") as f:
                            run_results_data.append(json.load(f))
                    except Exception:
                        pass
                if not run_results_data and exec_results:
                    run_results_data.append(exec_results)

                healing_cfg = HealingConfig(
                    project_id=proj_id,
                    target_url=proj_url,
                    workspace_dir=str(project_dir),
                    run_ids=[run_id],
                    scenarios=[tc.to_dict() for tc in approved_tcs],
                    run_results=run_results_data,
                    prd_text=proj_prd,
                    scope_instructions=proj_scope,
                )

                healing_res = healer.analyze_and_heal(
                    config=healing_cfg,
                    log_callback=log_callback,
                    cancel_check=cancel_event.is_set,
                )

                total_app_defects += healing_res.app_defects_count
                total_auto_failures += healing_res.automation_failures_count

                # 2. Check for healable automation failures
                healable_analyses = [a for a in healing_res.analyses if a.verdict == "NEEDS_FIX" or a.failure_origin == "AUTOMATION_FAILURE"]

                if not healable_analyses:
                    log_callback("INFO", f"[Healer] All remaining failures ({healing_res.app_defects_count}) are verified Application Product Defects. Test automation logic is valid. Halting heal loop.")
                    break

                log_callback("INFO", f"[Healer] Found {len(healable_analyses)} healable automation issue(s). Regenerating resilient test scripts...")

                # 3. Regenerate target scripts with healing notes
                target_sc_ids = {a.scenario_id for a in healable_analyses if a.scenario_id}
                if not target_sc_ids:
                    target_sc_ids = {tc.id for tc in approved_tcs if tc.healing_notes}

                regen_tcs = TestCase.query.filter(TestCase.id.in_(target_sc_ids)).all() if target_sc_ids else approved_tcs
                regen_data = [tc.to_dict() for tc in regen_tcs]

                regen_config = GeneratorConfig(
                    project_id=proj_id,
                    target_url=proj_url,
                    auth_type=proj_auth_type,
                    credentials=proj_credentials,
                    scope_instructions=proj_scope,
                    workspace_dir=str(project_dir),
                    run_id=run_id,
                    scenarios=regen_data,
                    prd_text=proj_prd,
                )

                regen_res = generator.generate(
                    config=regen_config,
                    log_callback=log_callback,
                    cancel_check=cancel_event.is_set,
                )

                # 4. Re-execute test suite
                log_callback("INFO", f"[Healer] Re-executing tests to verify healed scripts (Iteration {heal_iteration}/{max_heal_loops})...")
                re_exec_results = runner.execute(
                    log_callback=log_callback,
                    cancel_check=cancel_event.is_set,
                )
                try:
                    wm.save_run_results(proj_id, run_id, re_exec_results)
                except Exception as e:
                    logger.warning(f"Could not save run results: {e}")
                exec_results = re_exec_results

                re_summary = re_exec_results.get("summary", {})
                re_failed = re_summary.get("failed", 0)
                re_passed = re_summary.get("passed", 0)

                healed_this_round = max(0, remaining_failures - re_failed)
                total_healed += healed_this_round
                remaining_failures = re_failed

                pipeline_stats["execution"]["passed"] = re_passed
                pipeline_stats["execution"]["failed"] = re_failed

                if remaining_failures == 0:
                    log_callback("INFO", f"🎉 Self-healing succeeded on iteration {heal_iteration}! All tests now passing.")
                    break
                else:
                    log_callback("WARN", f"[Healer] Iteration {heal_iteration} complete. Remaining failures: {remaining_failures}.")

            if remaining_failures > 0 and heal_iteration >= max_heal_loops:
                log_callback("WARN", f"[Healer] Maximum self-healing limit ({max_heal_loops}/{max_heal_loops} iterations) reached. Pipeline finishing with remaining issues flagged.")

        pipeline_stats["healing"] = {
            "iterations_run": heal_iteration,
            "max_iterations": max_heal_loops,
            "app_defects_count": total_app_defects,
            "automation_failures_count": total_auto_failures,
            "healed_count": total_healed,
        }

        # Finalize run
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        if run.started_at:
            run.duration_ms = int((run.completed_at - run.started_at).total_seconds() * 1000)

        update_stage("completed", 100)

        log_callback(
            "INFO",
            f"✅ Autonomous End-to-End QA Pipeline Finished! "
            f"Routes: {pipeline_stats['exploration'].get('discovered_routes', 1)}, "
            f"Scenarios: {pipeline_stats['review'].get('approved', 0)} approved, "
            f"Execution: {pipeline_stats['execution'].get('passed', 0)} passed / {pipeline_stats['execution'].get('failed', 0)} failed, "
            f"Healed: {total_healed} (Heal loops: {heal_iteration}/{max_heal_loops}).",
            pipeline_stats,
        )

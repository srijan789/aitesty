import json
from flask import Blueprint, jsonify, request, current_app, abort
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan, TestCase
from app.models.test_run import TestRun, RunLog
from app.core.workspace import WorkspaceManager
from app.core.orchestrator import TestOrchestrator
from app.core.task_runner import task_runner

api_bp = Blueprint("api", __name__, url_prefix="/api")

def get_wm() -> WorkspaceManager:
    return WorkspaceManager(current_app.config["WORKSPACES_ROOT"])

@api_bp.route("/projects/<project_id>/explore", methods=["POST"])
def trigger_exploration(project_id):
    try:
        run = TestOrchestrator.trigger_exploration(project_id, trigger_source="api")
        return jsonify({
            "success": True,
            "run_id": run.id,
            "status": run.status,
            "message": "Exploration agent queued.",
        }), 202
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/projects/<project_id>/generate-tests", methods=["POST"])
def trigger_test_generation(project_id):
    try:
        data = request.get_json(silent=True) or {}
        scenario_ids = data.get("scenario_ids")
        run = TestOrchestrator.trigger_test_generation(
            project_id=project_id,
            scenario_ids=scenario_ids,
            trigger_source="api",
        )
        return jsonify({
            "success": True,
            "run_id": run.id,
            "status": run.status,
            "message": "Test creation agent queued.",
        }), 202
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route("/projects/<project_id>/execute-tests", methods=["POST"])
def trigger_test_execution(project_id):
    try:
        data = request.get_json(silent=True) or {}
        target_file = data.get("target_file")
        scenario_id = data.get("scenario_id")
        run = TestOrchestrator.trigger_test_execution(
            project_id=project_id,
            target_file=target_file,
            scenario_id=scenario_id,
            trigger_source="api",
        )
        return jsonify({
            "success": True,
            "run_id": run.id,
            "status": run.status,
            "target_file": target_file,
            "message": "Test execution queued.",
        }), 202
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/runs/<run_id>/status", methods=["GET"])
def get_run_status(run_id):
    run = db.get_or_404(TestRun, run_id)
    return jsonify(run.to_dict())

@api_bp.route("/runs/<run_id>/logs", methods=["GET"])
def get_run_logs(run_id):
    run = db.get_or_404(TestRun, run_id)
    after_id = request.args.get("after_id", 0, type=int)

    logs_query = (
        RunLog.query.filter(RunLog.run_id == run_id, RunLog.id > after_id)
        .order_by(RunLog.id.asc())
        .limit(200)
    )
    logs = [log.to_dict() for log in logs_query.all()]

    return jsonify({
        "run_id": run.id,
        "status": run.status,
        "completed": run.status in ["completed", "failed", "cancelled"],
        "logs": logs,
        "latest_log_id": logs[-1]["id"] if logs else after_id,
        "summary_stats": run.get_summary_stats(),
    })

@api_bp.route("/runs/<run_id>/logs/raw", methods=["GET"])
def get_run_logs_raw(run_id):
    from flask import Response
    run = db.get_or_404(TestRun, run_id)
    wm = get_wm()
    raw = wm.read_run_log_file(run.project_id, run.id)
    if not raw:
        logs = RunLog.query.filter_by(run_id=run.id).order_by(RunLog.id.asc()).all()
        raw = "\n".join([f"[{log.timestamp.strftime('%H:%M:%S') if log.timestamp else ''}] [{log.level}] {log.message}" for log in logs])
    return Response(raw or "No logs recorded for this run.", mimetype="text/plain")


@api_bp.route("/runs/<run_id>/cancel", methods=["POST"])
def cancel_run(run_id):
    run = db.get_or_404(TestRun, run_id)
    if run.status in ["completed", "failed", "cancelled"]:
        return jsonify({"success": False, "message": f"Run is already {run.status}."}), 400

    cancelled = task_runner.cancel_task(run_id)
    if not cancelled:
        # If not active in memory runner, mark DB directly
        run.status = "cancelled"
        db.session.commit()

    return jsonify({"success": True, "message": "Cancellation signal sent."})

@api_bp.route("/projects/<project_id>/test-plan", methods=["GET"])
def get_test_plan(project_id):
    project = db.get_or_404(Project, project_id)
    active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first()
    if active_plan:
        return jsonify(active_plan.to_dict())

    # Fall back to disk if not in DB
    wm = get_wm()
    plan_json = wm.load_test_plan_json(project.id)
    if plan_json:
        return jsonify(plan_json)
    return jsonify({"message": "No test plan found for project"}), 404

@api_bp.route("/projects/<project_id>/test-plan", methods=["PUT"])
def update_test_plan(project_id):
    project = db.get_or_404(Project, project_id)
    data = request.get_json()
    if not data or "scenarios" not in data:
        return jsonify({"error": "Invalid payload: scenarios array required"}), 400

    active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first()
    if not active_plan:
        active_plan = TestPlan(
            project_id=project.id,
            version=1,
            status="active",
            summary=data.get("summary", f"Test Plan for {project.name}"),
        )
        db.session.add(active_plan)
        db.session.flush()

    # Clear existing test cases and re-populate from edited list
    TestCase.query.filter_by(test_plan_id=active_plan.id).delete()

    for idx, sc in enumerate(data["scenarios"]):
        tc = TestCase(
            test_plan_id=active_plan.id,
            title=sc.get("title", f"Scenario {idx+1}"),
            category=sc.get("category", "happy_path"),
            priority=sc.get("priority", "P1"),
            preconditions=sc.get("preconditions"),
            description=sc.get("description", ""),
            expected_result=sc.get("expected_result", ""),
            pass_fail_criteria=sc.get("pass_fail_criteria"),
            script_path=sc.get("script_path"),
            status=sc.get("status", "pending_review"),
            execution_order=idx,
        )
        tc.set_steps(sc.get("steps", []))
        db.session.add(tc)

    db.session.commit()

    # Sync to workspace filesystem
    wm = get_wm()
    wm.save_test_plan(project.id, data)

    return jsonify({"success": True, "message": "Test plan updated successfully."})

@api_bp.route("/projects/<project_id>/scenarios/<scenario_id>/toggle-automation", methods=["POST"])
def toggle_scenario_automation(project_id, scenario_id):
    project = db.get_or_404(Project, project_id)
    active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first_or_404()
    tc = TestCase.query.filter_by(id=scenario_id, test_plan_id=active_plan.id).first_or_404()

    target_status = request.get_json(silent=True) or {}
    explicit_status = target_status.get("status")

    if explicit_status:
        tc.status = explicit_status
    elif tc.status == "marked_for_automation":
        tc.status = "pending_review"
    else:
        tc.status = "marked_for_automation"

    db.session.commit()

    # Sync to workspace filesystem
    wm = get_wm()
    wm.save_test_plan(project.id, active_plan.to_dict())

    return jsonify({
        "success": True,
        "scenario_id": tc.id,
        "new_status": tc.status,
        "message": f"Scenario '{tc.title}' status updated to {tc.status}."
    })

@api_bp.route("/projects/<project_id>/scenarios/bulk-mark-automation", methods=["POST"])
def bulk_mark_automation(project_id):
    project = db.get_or_404(Project, project_id)
    active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first_or_404()
    
    payload = request.get_json(silent=True) or {}
    status_to_set = payload.get("status", "marked_for_automation")
    scenario_ids = payload.get("scenario_ids")  # optional list of specific IDs

    query = TestCase.query.filter_by(test_plan_id=active_plan.id)
    if scenario_ids and isinstance(scenario_ids, list):
        query = query.filter(TestCase.id.in_(scenario_ids))

    updated_count = query.update({TestCase.status: status_to_set}, synchronize_session="fetch")
    db.session.commit()

    wm = get_wm()
    wm.save_test_plan(project.id, active_plan.to_dict())

    return jsonify({
        "success": True,
        "updated_count": updated_count,
        "new_status": status_to_set,
        "message": f"Updated {updated_count} scenarios to {status_to_set}."
    })

@api_bp.route("/projects/<project_id>/scenarios/<scenario_id>", methods=["DELETE"])
def delete_scenario(project_id, scenario_id):
    project = db.get_or_404(Project, project_id)
    active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first_or_404()
    tc = TestCase.query.filter_by(id=scenario_id, test_plan_id=active_plan.id).first_or_404()

    scenario_title = tc.title
    db.session.delete(tc)
    db.session.commit()

    # Re-sync updated test plan to workspace files
    wm = get_wm()
    wm.save_test_plan(project.id, active_plan.to_dict())

    return jsonify({
        "success": True,
        "scenario_id": scenario_id,
        "message": f"Scenario '{scenario_title}' deleted successfully.",
        "remaining_scenarios_count": len(active_plan.test_cases),
    })


@api_bp.route("/projects/<project_id>/files", methods=["GET"])
def list_files(project_id):
    project = db.get_or_404(Project, project_id)
    wm = get_wm()
    files = wm.list_test_files(project.id)
    return jsonify({"files": files})

@api_bp.route("/projects/<project_id>/files/content", methods=["GET"])
def get_file_content(project_id):
    project = db.get_or_404(Project, project_id)
    file_path = request.args.get("path", "")
    if not file_path:
        return jsonify({"error": "path parameter required"}), 400
    try:
        wm = get_wm()
        content = wm.read_test_file(project.id, file_path)
        return jsonify({"path": file_path, "content": content})
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@api_bp.route("/projects/<project_id>/files/content", methods=["PUT"])
def save_file_content(project_id):
    project = db.get_or_404(Project, project_id)
    data = request.get_json() or {}
    file_path = data.get("path", "")
    content = data.get("content", "")
    if not file_path:
        return jsonify({"error": "path is required"}), 400

    try:
        wm = get_wm()
        wm.save_test_file(project.id, file_path, content)
        return jsonify({"success": True, "message": f"Saved {file_path}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route("/projects/<project_id>/files", methods=["DELETE"])
def delete_file(project_id):
    project = db.get_or_404(Project, project_id)
    file_path = request.args.get("path") or (request.get_json(silent=True) or {}).get("path")
    if not file_path:
        return jsonify({"error": "path parameter is required"}), 400

    safe_rel = file_path.lstrip("/").replace("../", "")
    if not safe_rel.startswith("tests/"):
        return jsonify({"error": "Can only delete files within tests/ directory"}), 400

    wm = get_wm()
    try:
        deleted = wm.delete_test_file(project.id, safe_rel)
        if not deleted:
            return jsonify({"error": f"File '{file_path}' not found."}), 404

        # Clean up any TestCase pointing to this script
        active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first()
        if active_plan:
            linked_cases = TestCase.query.filter_by(test_plan_id=active_plan.id, script_path=safe_rel).all()
            for tc in linked_cases:
                tc.script_path = None
                if tc.status == "automated":
                    tc.status = "marked_for_automation"
            if linked_cases:
                db.session.commit()
                wm.save_test_plan(project.id, active_plan.to_dict())

        return jsonify({"success": True, "message": f"Successfully deleted '{safe_rel}'."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route("/runs/<run_id>/report", methods=["GET"])
def get_run_report(run_id):
    run = db.get_or_404(TestRun, run_id)
    wm = get_wm()
    run_dir = wm.get_run_dir(run.project_id, run.id)
    json_path = run_dir / "results.json"
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({
        "run_id": run.id,
        "summary": run.get_summary_stats(),
        "status": run.status,
        "message": "Detailed report not yet compiled for this run."
    })

@api_bp.route("/runs/<run_id>/report/html", methods=["GET"])
def get_run_report_html(run_id):
    from flask import Response
    run = db.get_or_404(TestRun, run_id)
    wm = get_wm()
    run_dir = wm.get_run_dir(run.project_id, run.id)
    html_path = run_dir / "report.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="text/html")
    
    # Generate on the fly if needed
    from app.core.report_generator import generate_html_report
    results = {
        "summary": run.get_summary_stats(),
        "tests": [],
    }
    html = generate_html_report(results, project_name="Project", run_id=run.id)
    return Response(html, mimetype="text/html")


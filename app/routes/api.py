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

@api_bp.route("/projects/<project_id>/execute-tests", methods=["POST"])
def trigger_test_execution(project_id):
    try:
        run = TestOrchestrator.trigger_test_execution(project_id, trigger_source="api")
        return jsonify({
            "success": True,
            "run_id": run.id,
            "status": run.status,
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
    wm = get_wm()
    plan_json = wm.load_test_plan_json(project.id)
    if not plan_json:
        # Fall back to active plan in DB
        active_plan = TestPlan.query.filter_by(project_id=project.id, status="active").first()
        if active_plan:
            plan_json = active_plan.to_dict()
        else:
            return jsonify({"message": "No test plan found for project"}), 404
    return jsonify(plan_json)

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
            description=sc.get("description", ""),
            expected_result=sc.get("expected_result", ""),
            script_path=sc.get("script_path"),
            status=sc.get("status", "pending"),
            execution_order=idx,
        )
        tc.set_steps(sc.get("steps", []))
        db.session.add(tc)

    db.session.commit()

    # Sync to workspace filesystem
    wm = get_wm()
    wm.save_test_plan(project.id, data)

    return jsonify({"success": True, "message": "Test plan updated successfully."})

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

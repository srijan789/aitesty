from flask import Blueprint, render_template, current_app, abort
from app.extensions import db
from app.models.project import Project
from app.models.test_plan import TestPlan
from app.models.test_run import TestRun
from app.core.workspace import WorkspaceManager

workspace_views_bp = Blueprint("workspace_views", __name__)

def get_wm() -> WorkspaceManager:
    return WorkspaceManager(current_app.config["WORKSPACES_ROOT"])

@workspace_views_bp.route("/projects/<project_id>")
def show(project_id):
    project = db.get_or_404(Project, project_id)
    wm = get_wm()

    # Get active test plan
    latest_plan = (
        TestPlan.query.filter_by(project_id=project.id, status="active")
        .order_by(TestPlan.version.desc())
        .first()
    )
    if not latest_plan:
        latest_plan = (
            TestPlan.query.filter_by(project_id=project.id)
            .order_by(TestPlan.version.desc())
            .first()
        )

    # Group test cases by category
    happy_paths = []
    edge_cases = []
    error_flows = []
    if latest_plan:
        for tc in latest_plan.test_cases:
            if tc.category == "happy_path":
                happy_paths.append(tc)
            elif tc.category == "edge_case":
                edge_cases.append(tc)
            elif tc.category == "error_flow":
                error_flows.append(tc)

    # Get test scripts in workspace/tests
    test_files = wm.list_test_files(project.id)

    # Get test runs
    runs = TestRun.query.filter_by(project_id=project.id).order_by(TestRun.started_at.desc()).all()

    # Workspace directory absolute path for UI display
    workspace_path = str(wm.get_project_dir(project.id))

    return render_template(
        "workspace/show.html",
        project=project,
        plan=latest_plan,
        happy_paths=happy_paths,
        edge_cases=edge_cases,
        error_flows=error_flows,
        test_files=test_files,
        runs=runs,
        workspace_path=workspace_path,
    )

@workspace_views_bp.route("/projects/<project_id>/runs/<run_id>")
def run_detail(project_id, run_id):
    project = db.get_or_404(Project, project_id)
    run = TestRun.query.filter_by(id=run_id, project_id=project.id).first_or_404()
    
    wm = get_wm()
    raw_logs = wm.read_run_log_file(project.id, run.id)
    test_log_files = wm.list_test_log_files(project.id, run.id)

    import json
    results_data = {}
    json_path = wm.get_run_dir(project.id, run.id) / "results.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                results_data = json.load(f)
        except Exception:
            pass

    healing_data = {}
    heal_path = wm.get_run_dir(project.id, run.id) / "healing_report.json"
    if heal_path.exists():
        try:
            with open(heal_path, "r", encoding="utf-8") as f:
                healing_data = json.load(f)
        except Exception:
            pass

    stats = run.get_summary_stats()

    return render_template(
        "workspace/run_detail.html",
        project=project,
        run=run,
        stats=stats,
        raw_logs=raw_logs,
        test_log_files=test_log_files,
        results_data=results_data,
        healing_data=healing_data,
    )

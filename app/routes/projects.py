from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.extensions import db
from app.models.project import Project
from app.core.workspace import WorkspaceManager

projects_bp = Blueprint("projects", __name__)

def get_wm() -> WorkspaceManager:
    return WorkspaceManager(current_app.config["WORKSPACES_ROOT"])

@projects_bp.route("/")
def root():
    return redirect(url_for("projects.index"))

@projects_bp.route("/projects")
def index():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("projects/index.html", projects=projects)

@projects_bp.route("/projects/new", methods=["GET"])
def create_form():
    return render_template("projects/create.html")

@projects_bp.route("/projects", methods=["POST"])
def create():
    name = request.form.get("name", "").strip()
    target_url = request.form.get("target_url", "").strip()
    description = request.form.get("description", "").strip()
    auth_type = request.form.get("auth_type", "none").strip()
    scope_instructions = request.form.get("scope_instructions", "").strip()
    prd_text = request.form.get("prd_text", "").strip()
    crawl_depth = request.form.get("crawl_depth", type=int) or 2
    max_pages = request.form.get("max_pages", type=int) or 10
    target_test_count = request.form.get("target_test_count", type=int) or 12
    exploration_strategy = request.form.get("exploration_strategy", "balanced").strip()

    if not name or not target_url:
        flash("Project Name and Target URL are required.", "error")
        return redirect(url_for("projects.create_form"))

    # Parse credentials based on auth_type
    creds = {}
    if auth_type == "form" or auth_type == "basic":
        username = request.form.get("auth_username", "").strip()
        password = request.form.get("auth_password", "").strip()
        if username:
            creds["username"] = username
        if password:
            creds["password"] = password
    elif auth_type == "bearer":
        token = request.form.get("auth_token", "").strip()
        if token:
            creds["token"] = token

    project = Project(
        name=name,
        target_url=target_url,
        description=description,
        auth_type=auth_type,
        scope_instructions=scope_instructions,
        prd_text=prd_text,
        crawl_depth=crawl_depth,
        max_pages=max_pages,
        target_test_count=target_test_count,
        exploration_strategy=exploration_strategy,
    )
    project.set_credentials(creds)

    db.session.add(project)
    db.session.commit()

    # Initialize workspace filesystem sandbox
    wm = get_wm()
    wm.init_project_workspace(project)

    flash(f"Project '{project.name}' successfully created.", "success")
    return redirect(url_for("workspace_views.show", project_id=project.id))

@projects_bp.route("/projects/<project_id>/edit", methods=["GET"])
def edit_form(project_id):
    project = db.get_or_404(Project, project_id)
    return render_template("projects/edit.html", project=project, creds=project.get_credentials())

@projects_bp.route("/projects/<project_id>/edit", methods=["POST"])
def update(project_id):
    project = db.get_or_404(Project, project_id)

    project.name = request.form.get("name", project.name).strip()
    project.target_url = request.form.get("target_url", project.target_url).strip()
    project.description = request.form.get("description", "").strip()
    project.auth_type = request.form.get("auth_type", "none").strip()
    project.scope_instructions = request.form.get("scope_instructions", "").strip()
    project.prd_text = request.form.get("prd_text", "").strip()
    if request.form.get("crawl_depth"):
        project.crawl_depth = request.form.get("crawl_depth", type=int)
    if request.form.get("max_pages"):
        project.max_pages = request.form.get("max_pages", type=int)
    if request.form.get("target_test_count"):
        project.target_test_count = request.form.get("target_test_count", type=int)
    if request.form.get("exploration_strategy"):
        project.exploration_strategy = request.form.get("exploration_strategy", "").strip()

    creds = {}
    if project.auth_type in ["form", "basic"]:
        username = request.form.get("auth_username", "").strip()
        password = request.form.get("auth_password", "").strip()
        # Keep existing password if not provided in edit
        existing_creds = project.get_credentials()
        if not password and "password" in existing_creds:
            password = existing_creds["password"]
        if username:
            creds["username"] = username
        if password:
            creds["password"] = password
    elif project.auth_type == "bearer":
        token = request.form.get("auth_token", "").strip()
        existing_creds = project.get_credentials()
        if not token and "token" in existing_creds:
            token = existing_creds["token"]
        if token:
            creds["token"] = token

    project.set_credentials(creds)
    db.session.commit()

    # Sync to workspace config.json
    wm = get_wm()
    wm.save_project_config(project)

    flash("Project settings updated successfully.", "success")
    return redirect(url_for("workspace_views.show", project_id=project.id))

@projects_bp.route("/projects/<project_id>/delete", methods=["POST"])
def delete(project_id):
    project = db.get_or_404(Project, project_id)
    project_name = project.name

    # Delete workspace directory
    wm = get_wm()
    wm.delete_project_workspace(project.id)

    db.session.delete(project)
    db.session.commit()

    flash(f"Project '{project_name}' and its workspace have been deleted.", "info")
    return redirect(url_for("projects.index"))

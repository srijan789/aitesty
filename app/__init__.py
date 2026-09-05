import os
from pathlib import Path
from flask import Flask
from config import Config
from app.extensions import db
from app.core.task_runner import task_runner
from app.routes.projects import projects_bp
from app.routes.workspace_views import workspace_views_bp
from app.routes.api import api_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance and workspace root folders exist
    basedir = Path(app.root_path).parent
    (basedir / "instance").mkdir(parents=True, exist_ok=True)
    Path(app.config["WORKSPACES_ROOT"]).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    task_runner.init_app(app)

    # Register blueprints
    app.register_blueprint(projects_bp)
    app.register_blueprint(workspace_views_bp)
    app.register_blueprint(api_bp)

    # Auto-create tables in development/testing
    with app.app_context():
        from app.models import Project, TestPlan, TestCase, TestRun, RunLog, PipelineRun, HealerAttempt  # noqa: F401
        db.create_all()
        # Backward-compatibility schema migration for existing SQLite files
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE projects ADD COLUMN prd_text TEXT"))
                except Exception:
                    pass
                for col_sql in [
                    "ALTER TABLE test_cases ADD COLUMN preconditions TEXT",
                    "ALTER TABLE test_cases ADD COLUMN pass_fail_criteria TEXT",
                    "ALTER TABLE test_cases ADD COLUMN priority VARCHAR(10) DEFAULT 'P1'",
                ]:
                    try:
                        conn.execute(text(col_sql))
                    except Exception:
                        pass
                conn.commit()
        except Exception:
            pass  # columns already exist or freshly created

    # Template filters/helpers
    @app.template_filter("timeago")
    def timeago_filter(dt):
        if not dt:
            return "never"
        from datetime import datetime
        diff = datetime.utcnow() - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"

    return app

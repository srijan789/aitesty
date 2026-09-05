import pytest
import shutil
from pathlib import Path
from app import create_app
from app.extensions import db
from app.models.project import Project
from config import TestingConfig

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
        # Clean up test workspaces
        if Path(app.config["WORKSPACES_ROOT"]).exists():
            shutil.rmtree(app.config["WORKSPACES_ROOT"], ignore_errors=True)

@pytest.fixture
def client(app):
    return app.test_client()

def test_create_project_initializes_db_and_workspace(client, app):
    res = client.post(
        "/projects",
        data={
            "name": "Acme Portal",
            "target_url": "https://portal.acme.com",
            "description": "Internal employee dashboard",
            "auth_type": "form",
            "auth_username": "testuser",
            "auth_password": "supersecretpassword",
            "scope_instructions": "Focus on invoices",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        project = Project.query.filter_by(name="Acme Portal").first()
        assert project is not None
        assert project.target_url == "https://portal.acme.com"
        assert project.auth_type == "form"
        creds = project.get_credentials()
        assert creds["username"] == "testuser"
        assert creds["password"] == "supersecretpassword"
        
        # Verify password masking
        masked = project.get_masked_credentials()
        assert masked["password"] == "••••••••"
        assert masked["username"] == "testuser"

        # Verify workspace directory exists
        ws_root = Path(app.config["WORKSPACES_ROOT"])
        p_dir = ws_root / project.id
        assert p_dir.exists()
        assert (p_dir / "config.json").exists()
        assert (p_dir / "tests").is_dir()
        assert (p_dir / "runs").is_dir()

def test_edit_project_updates_config(client, app):
    # First create project
    client.post(
        "/projects",
        data={"name": "Initial Name", "target_url": "https://init.example.com", "auth_type": "none"},
        follow_redirects=True,
    )
    with app.app_context():
        project = Project.query.filter_by(name="Initial Name").first()
        p_id = project.id

    # Now edit
    res = client.post(
        f"/projects/{p_id}/edit",
        data={"name": "Updated Name", "target_url": "https://updated.example.com", "auth_type": "none"},
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        updated = db.session.get(Project, p_id)
        assert updated.name == "Updated Name"
        assert updated.target_url == "https://updated.example.com"

def test_delete_project_removes_workspace(client, app):
    client.post(
        "/projects",
        data={"name": "To Delete", "target_url": "https://delete.example.com", "auth_type": "none"},
        follow_redirects=True,
    )
    with app.app_context():
        project = Project.query.filter_by(name="To Delete").first()
        p_id = project.id
        p_dir = Path(app.config["WORKSPACES_ROOT"]) / p_id
        assert p_dir.exists()

    res = client.post(f"/projects/{p_id}/delete", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        assert db.session.get(Project, p_id) is None
        assert not p_dir.exists()

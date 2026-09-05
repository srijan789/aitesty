import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-secret-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'aitesty.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WORKSPACES_ROOT = Path(os.environ.get("WORKSPACES_ROOT", BASE_DIR / "workspaces"))
    MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", 4))
    EXPLORER_AGENT_TYPE = os.environ.get("EXPLORER_AGENT_TYPE", "mock")

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WORKSPACES_ROOT = BASE_DIR / "tests" / "test_workspaces"
    MAX_CONCURRENT_TASKS = 2

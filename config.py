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
<<<<<<< HEAD
    EXPLORER_AGENT_TYPE = os.environ.get("EXPLORER_AGENT_TYPE", "mock")
    GENERATOR_AGENT_TYPE = os.environ.get("GENERATOR_AGENT_TYPE", "mock")
    HEALER_AGENT_TYPE = os.environ.get("HEALER_AGENT_TYPE", "mock")

    MAX_REPLAN_CYCLES = int(os.environ.get("MAX_REPLAN_CYCLES", 2))
    MAX_HEAL_ATTEMPTS = int(os.environ.get("MAX_HEAL_ATTEMPTS", 3))
    COVERAGE_THRESHOLD = float(os.environ.get("COVERAGE_THRESHOLD", 0.6))
=======
    EXPLORER_AGENT_TYPE = os.environ.get("EXPLORER_AGENT_TYPE", "playwright")
    GENERATOR_AGENT_TYPE = os.environ.get("GENERATOR_AGENT_TYPE", "mock")
    HEALER_AGENT_TYPE = os.environ.get("HEALER_AGENT_TYPE", "mock")

    MAX_REPLAN_CYCLES = int(os.environ.get("MAX_REPLAN_CYCLES", 2))
    MAX_HEAL_ATTEMPTS = int(os.environ.get("MAX_HEAL_ATTEMPTS", 3))
    COVERAGE_THRESHOLD = float(os.environ.get("COVERAGE_THRESHOLD", 0.6))

    # LLM Gateway Configuration
    TRUEFOUNDRY_API_KEY = os.environ.get(
        "TRUEFOUNDRY_API_KEY",
        "tfy_pat_default-u3n8eaqjipdolz2w8cz3uhcm_0E2iyumk9OfB7Vo68461d1270ac232560fa7cdd084688708",
    )
    TRUEFOUNDRY_BASE_URL = os.environ.get("TRUEFOUNDRY_BASE_URL", "https://gateway.truefoundry.ai")
    EXPLORER_MODEL = os.environ.get("EXPLORER_MODEL", "openrouter/google-gemini-3.7-flash")
>>>>>>> 145374c (Added the Exploratory + test planning agent)

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WORKSPACES_ROOT = BASE_DIR / "tests" / "test_workspaces"
    MAX_CONCURRENT_TASKS = 2
    EXPLORER_AGENT_TYPE = "mock"

# Aitesty - Autonomous Test Orchestration Platform

A unified, monolithic Flask web platform and background agent orchestrator for autonomous quality engineering.

---

## Architecture Overview

- **Monolith Core**: Flask application factory with server-rendered Jinja2 templates, styled with modern Tailwind CSS CDN and custom terminal/log UI.
- **Persistence Layer**: SQLite via SQLAlchemy (`Project`, `TestPlan`, `TestCase`, `TestRun`, `RunLog`).
- **Filesystem Workspace Isolation**: Each target application is assigned an isolated workspace in `workspaces/<project_id>/` containing:
  - `config.json`: Metadata, target URLs, and secure credentials.
  - `test_plan.json` & `test_plan.md`: Discovered test plans with categorized scenarios.
  - `tests/*.spec.py`: Executable test specifications.
  - `runs/<run_id>/`: Execution artifacts including `execution.log`, `results.json`, screenshots, and traces.
- **Pluggable Background Task Runner**: Non-blocking thread-pool engine with Flask application context binding, status tracking, cancellation tokens, and synchronous database/disk logging.
- **Explorer Sub-Agent Contract**: Pre-architected interface (`BaseExplorerAgent`, `ExplorerConfig`, `ExplorerResult`) with a Stage 1 Mock Explorer and ready hooks for Stage 2 Playwright Autonomous Exploration.

---

## Directory Structure

```text
aitesty/
├── wsgi.py                     # WSGI Application Entry Point
├── config.py                   # Platform Configuration & Workspace Paths
├── requirements.txt            # Python Dependencies
├── app/
│   ├── __init__.py             # Flask App Factory (create_app)
│   ├── extensions.py           # SQLAlchemy extension
│   ├── models/                 # SQLAlchemy Data Models
│   │   ├── project.py          # Project model & credentials handling
│   │   ├── test_plan.py        # TestPlan & TestCase models
│   │   └── test_run.py         # TestRun & RunLog models
│   ├── core/                   # Platform Infrastructure
│   │   ├── workspace.py        # WorkspaceManager (filesystem sandbox)
│   │   ├── task_runner.py      # Thread-safe background task runner
│   │   └── orchestrator.py     # TestOrchestrator coordinating tasks and plans
│   ├── agents/                 # Agent Interfaces & Sub-Agents
│   │   ├── base.py             # BaseExplorerAgent contract & dataclasses
│   │   ├── mock_explorer.py    # Stage 1 Mock Explorer Agent
│   │   └── registry.py         # Agent registry and factory loader
│   ├── routes/                 # Flask Blueprints
│   │   ├── projects.py         # Project CRUD routes
│   │   ├── workspace_views.py  # Workspace tabs & run detail views
│   │   └── api.py              # REST API for exploration, runs, plans, files
│   ├── templates/              # Jinja2 Templates (Tailwind styled)
│   │   ├── base.html
│   │   ├── projects/           # Projects listing, creation, and settings
│   │   └── workspace/          # Tabbed overview, plan cards, test editor, console
│   └── static/                 # CSS & JavaScript
│       ├── css/custom.css
│       └── js/
│           ├── app.js
│           ├── log_stream.js   # Real-time console poller
│           └── plan_editor.js  # Interactive test plan editor
├── workspaces/                 # Project workspaces (git-ignored)
└── tests/                      # Automated test suite (Pytest)
```

---

## Quickstart

### 1. Setup & Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Platform
```bash
python3 wsgi.py
```
Open [http://127.0.0.1:5050](http://127.0.0.1:5050) in your web browser.

### 3. Run Automated Tests
```bash
pytest tests/ -v
```

---

## Explorer Sub-Agent Interface (Stage 2 Hook)

The platform is designed to plug directly into the upcoming autonomous Playwright crawler. Implementations simply subclass `BaseExplorerAgent`:

```python
from app.agents.base import BaseExplorerAgent, ExplorerConfig, ExplorerResult

class PlaywrightExplorerAgent(BaseExplorerAgent):
    def explore(self, config: ExplorerConfig, log_callback, cancel_check=None) -> ExplorerResult:
        # 1. Autonomous Playwright browser execution using config.target_url and config.credentials
        # 2. Emit real-time progress via log_callback(level, message, metadata)
        # 3. Return structured ExplorerResult with discovered scenarios
        ...
```
Register the agent in `app/agents/registry.py` or configure via `EXPLORER_AGENT_TYPE = "playwright"`.

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

class WorkspaceManager:
    """
    Manages isolated per-project filesystem workspaces:
    workspaces/<project_id>/
      ├── config.json
      ├── test_plan.json
      ├── test_plan.md
      ├── tests/
      │   └── *.spec.py
      └── runs/
          └── <run_id>/
              ├── execution.log
              ├── results.json
              ├── screenshots/
              └── traces/
    """

    def __init__(self, workspaces_root: Path):
        self.root = Path(workspaces_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def get_project_dir(self, project_id: str) -> Path:
        p_dir = (self.root / project_id).resolve()
        # Security check: ensure path does not escape workspaces_root
        if not str(p_dir).startswith(str(self.root)):
            raise ValueError("Invalid project workspace path traversal attempt")
        return p_dir

    def init_project_workspace(self, project) -> Path:
        """Initializes project workspace directories and writes config.json."""
        project_dir = self.get_project_dir(project.id)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "tests").mkdir(parents=True, exist_ok=True)
        (project_dir / "runs").mkdir(parents=True, exist_ok=True)

        self.save_project_config(project)
        return project_dir

    def save_project_config(self, project) -> Path:
        project_dir = self.get_project_dir(project.id)
        config_file = project_dir / "config.json"
        
        config_data = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "target_url": project.target_url,
            "auth_type": project.auth_type,
            "credentials": project.get_credentials(),
            "scope_instructions": project.scope_instructions,
            "prd_text": getattr(project, "prd_text", None),
            "created_at": project.created_at.isoformat() if project.created_at else datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        return config_file

    def get_project_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        config_file = self.get_project_dir(project_id) / "config.json"
        if not config_file.exists():
            return None
        with open(config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def delete_project_workspace(self, project_id: str) -> bool:
        project_dir = self.get_project_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
            return True
        return False

    def save_test_plan(self, project_id: str, plan_data: Dict[str, Any], markdown_content: str = "") -> Dict[str, Path]:
        project_dir = self.get_project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        json_path = project_dir / "test_plan.json"
        md_path = project_dir / "test_plan.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(plan_data, f, indent=2)

        if not markdown_content:
            markdown_content = self.generate_markdown_from_plan(plan_data)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return {"json_path": json_path, "md_path": md_path}

    def load_test_plan_json(self, project_id: str) -> Optional[Dict[str, Any]]:
        json_path = self.get_project_dir(project_id) / "test_plan.json"
        if not json_path.exists():
            return None
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_test_plan_md(self, project_id: str) -> Optional[str]:
        md_path = self.get_project_dir(project_id) / "test_plan.md"
        if not md_path.exists():
            return None
        with open(md_path, "r", encoding="utf-8") as f:
            return f.read()

    def generate_markdown_from_plan(self, plan_data: Dict[str, Any]) -> str:
        """Helper to convert structured JSON plan to readable Markdown."""
        lines = [
            f"# Test Plan: {plan_data.get('summary', 'Application Exploration')}",
            f"\nVersion: {plan_data.get('version', 1)} | Status: {plan_data.get('status', 'active')}",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n",
            "## Discovered Scenarios\n",
        ]

        scenarios = plan_data.get("scenarios", [])
        categories = {
            "happy_path": "✅ Happy Path Scenarios",
            "edge_case": "⚠️ Edge Cases & Boundary Conditions",
            "error_flow": "🛑 Error Handling & Negative Flows",
        }

        for cat_key, cat_title in categories.items():
            cat_scenarios = [s for s in scenarios if s.get("category") == cat_key]
            if cat_scenarios:
                lines.append(f"### {cat_title}\n")
                for s in cat_scenarios:
                    priority = s.get("priority", "P1")
                    status = s.get("status", "pending_review")
                    lines.append(f"#### [{priority}] {s.get('title', 'Scenario')} `({status})`")
                    if s.get("description"):
                        lines.append(f"{s['description']}\n")
                    if s.get("preconditions"):
                        lines.append(f"**Preconditions:** {s['preconditions']}\n")
                    steps = s.get("steps", [])
                    if steps:
                        lines.append("**Execution Steps:**")
                        for idx, step in enumerate(steps, 1):
                            if isinstance(step, dict):
                                action = step.get("action", "")
                                target = step.get("target_element", "")
                                outcome = step.get("expected_outcome", "")
                                target_str = f" on `{target}`" if target else ""
                                outcome_str = f" -> {outcome}" if outcome else ""
                                lines.append(f"{idx}. {action}{target_str}{outcome_str}")
                            else:
                                lines.append(f"{idx}. {step}")
                        lines.append("")
                    if s.get("expected_result"):
                        lines.append(f"**Expected Output:** {s['expected_result']}\n")
                    if s.get("pass_fail_criteria"):
                        lines.append(f"**Pass / Fail Criteria:** {s['pass_fail_criteria']}\n")
                lines.append("---\n")

        return "\n".join(lines)

    def init_run_dir(self, project_id: str, run_id: str) -> Path:
        run_dir = self.get_project_dir(project_id) / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "screenshots").mkdir(parents=True, exist_ok=True)
        (run_dir / "traces").mkdir(parents=True, exist_ok=True)
        (run_dir / "test_logs").mkdir(parents=True, exist_ok=True)
        
        # Touch initial execution.log
        log_file = run_dir / "execution.log"
        if not log_file.exists():
            log_file.write_text(f"[{datetime.utcnow().isoformat()}] [INFO] Run {run_id} initialized.\n")

        return run_dir

    def get_run_dir(self, project_id: str, run_id: str) -> Path:
        return self.get_project_dir(project_id) / "runs" / run_id

    def append_run_log_file(self, project_id: str, run_id: str, level: str, message: str):
        run_dir = self.get_run_dir(project_id, run_id)
        if not run_dir.exists():
            self.init_run_dir(project_id, run_id)
        log_file = run_dir / "execution.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]}] [{level.upper()}] {message}\n")

    def read_run_log_file(self, project_id: str, run_id: str) -> str:
        log_file = self.get_run_dir(project_id, run_id) / "execution.log"
        if not log_file.exists():
            return ""
        with open(log_file, "r", encoding="utf-8") as f:
            return f.read()

    def append_test_log_file(self, project_id: str, run_id: str, test_name: str, level: str, message: str):
        """Appends a log line to an isolated per-testcase log file."""
        run_dir = self.get_run_dir(project_id, run_id)
        test_logs_dir = run_dir / "test_logs"
        test_logs_dir.mkdir(parents=True, exist_ok=True)
        clean_name = "".join(c for c in test_name if c.isalnum() or c in ("-", "_")).strip() or "test"
        log_file = test_logs_dir / f"{clean_name}.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]}] [{level.upper()}] {message}\n")

    def read_test_log_file(self, project_id: str, run_id: str, test_name: str) -> str:
        """Reads isolated log lines for a specific testcase."""
        run_dir = self.get_run_dir(project_id, run_id)
        clean_name = "".join(c for c in test_name if c.isalnum() or c in ("-", "_")).strip() or "test"
        log_file = run_dir / "test_logs" / f"{clean_name}.log"
        if not log_file.exists():
            return ""
        with open(log_file, "r", encoding="utf-8") as f:
            return f.read()

    def list_test_log_files(self, project_id: str, run_id: str) -> List[str]:
        """Lists test names that have isolated log files."""
        run_dir = self.get_run_dir(project_id, run_id)
        test_logs_dir = run_dir / "test_logs"
        if not test_logs_dir.exists():
            return []
        return sorted([p.stem for p in test_logs_dir.glob("*.log")])

    def save_run_results(self, project_id: str, run_id: str, results_data: Dict[str, Any]) -> Path:
        """Saves execution results.json for a test run."""
        run_dir = self.get_run_dir(project_id, run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        results_file = run_dir / "results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results_data, f, indent=2)
        return results_file

    def load_run_results(self, project_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        """Loads execution results.json for a test run if it exists."""
        results_file = self.get_run_dir(project_id, run_id) / "results.json"
        if not results_file.exists():
            return None
        with open(results_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_test_files(self, project_id: str) -> List[Dict[str, Any]]:
        tests_dir = self.get_project_dir(project_id) / "tests"
        if not tests_dir.exists():
            return []
        files = []
        for p in tests_dir.glob("*.py"):
            stat = p.stat()
            subtests = []
            try:
                import ast
                content = p.read_text(encoding="utf-8")
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        docstring = ast.get_docstring(node) or ""
                        subtest_title = node.name.replace("test_", "").replace("_", " ").title()
                        for line in docstring.split("\n"):
                            clean_line = line.strip()
                            if "Subtest:" in clean_line:
                                subtest_title = clean_line.split("Subtest:")[-1].strip()
                        subtests.append({
                            "name": node.name,
                            "title": subtest_title,
                        })
            except Exception:
                pass

            files.append({
                "name": p.name,
                "path": f"tests/{p.name}",
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "subtests": subtests,
            })
        for p in tests_dir.glob("*.ts"):
            stat = p.stat()
            files.append({
                "name": p.name,
                "path": f"tests/{p.name}",
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "subtests": [],
            })
        return sorted(files, key=lambda x: x["name"])

    def read_test_file(self, project_id: str, relative_path: str) -> str:
        safe_rel = relative_path.lstrip("/").replace("../", "")
        file_path = self.get_project_dir(project_id) / safe_rel
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def save_test_file(self, project_id: str, relative_path: str, content: str) -> Path:
        safe_rel = relative_path.lstrip("/").replace("../", "")
        file_path = self.get_project_dir(project_id) / safe_rel
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def delete_test_file(self, project_id: str, relative_path: str) -> bool:
        """Safely delete a test file within the project tests/ directory."""
        safe_rel = relative_path.lstrip("/").replace("../", "")
        if not safe_rel.startswith("tests/"):
            raise ValueError("Can only delete files within tests/ directory")
        file_path = self.get_project_dir(project_id) / safe_rel
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
        return False

from pathlib import Path
from typing import Dict, Any, Optional, Callable

from app.agents.base import (
    BaseGeneratorAgent,
    GeneratorConfig,
    GeneratorResult,
    GeneratedTestFile,
)

class MockGeneratorAgent(BaseGeneratorAgent):
    """
    Deterministic Mock Generator Agent for offline testing and test suites.
    """

    def generate(
        self,
        config: GeneratorConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> GeneratorResult:
        log_callback("INFO", f"Executing Mock Generator for project {config.project_id}")

        scenarios = config.scenarios or []
        if not scenarios:
            log_callback("WARN", "No scenarios marked for mock generation.")
            return GeneratorResult(status="success", generated_files=[], automated_scenario_ids=[])

        workspace_path = Path(config.workspace_dir)
        tests_dir = workspace_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        filename = "test_mock_suite.spec.py"
        file_path = tests_dir / filename

        code_lines = [
            '"""Mock Generated Test Suite"""',
            'import pytest',
            'from playwright.sync_api import Page, expect',
            '',
            f'TARGET_URL = "{config.target_url}"',
            '',
        ]

        sc_ids = []
        for idx, s in enumerate(scenarios, 1):
            sc_id = s.get("id", f"mock-{idx}")
            sc_ids.append(sc_id)
            title = s.get("title", f"Scenario {idx}")
            clean_name = f"test_mock_scenario_{idx}"
            code_lines.extend([
                f"def {clean_name}(page: Page):",
                f'    """Scenario: {title}"""',
                '    page.goto(TARGET_URL)',
                '    expect(page.locator("body")).to_be_visible()',
                '',
            ])

        content = "\n".join(code_lines)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        gen_file = GeneratedTestFile(
            filename=filename,
            relative_path=f"tests/{filename}",
            content=content,
            scenario_ids=sc_ids,
            test_count=len(scenarios),
        )

        log_callback("INFO", f"Mock generator created: tests/{filename} with {len(scenarios)} tests.")

        return GeneratorResult(
            status="success",
            generated_files=[gen_file],
            automated_scenario_ids=sc_ids,
            artifacts_created=[str(file_path)],
        )

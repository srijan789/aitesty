import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from openai import OpenAI
from app.agents.base import (
    BaseGeneratorAgent,
    GeneratorConfig,
    GeneratorResult,
    GeneratedTestFile,
)

logger = logging.getLogger(__name__)

GENERATOR_MCP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_test_spec_file",
            "description": "Output a complete executable Python Playwright test specification file for a group of scenarios.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename for the spec file, e.g. 'test_happy_path.spec.py' or 'test_authentication.spec.py'."
                    },
                    "description": {
                        "type": "string",
                        "description": "Summary of scenarios covered in this spec file."
                    },
                    "scenario_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of scenario IDs covered in this file."
                    },
                    "code_content": {
                        "type": "string",
                        "description": "Full, syntactically valid Python code containing pytest/Playwright test functions, step logs, assertions, and failure screenshot handlers."
                    }
                },
                "required": ["filename", "scenario_ids", "code_content"]
            }
        }
    }
]

class PlaywrightGeneratorAgent(BaseGeneratorAgent):
    """
    Autonomous Test Creation Agent powered by Gemini 3.7 Flash via TrueFoundry Gateway.
    Reads human-reviewed QA test plan scenarios marked for automation and translates them
    into executable, maintainable Python Playwright test specs with structured telemetry.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get(
            "TRUEFOUNDRY_API_KEY",
            "tfy_pat_default-u3n8eaqjipdolz2w8cz3uhcm_0E2iyumk9OfB7Vo68461d1270ac232560fa7cdd084688708",
        )
        self.base_url = base_url or os.environ.get("TRUEFOUNDRY_BASE_URL", "https://gateway.truefoundry.ai")
        self.model = model or os.environ.get("GENERATOR_MODEL", "openrouter/google-gemini-3.7-flash")

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate(
        self,
        config: GeneratorConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> GeneratorResult:
        def is_cancelled() -> bool:
            if cancel_check and cancel_check():
                log_callback("WARN", "Test creation cancelled by user request.", None)
                return True
            return False

        log_callback("INFO", f"Launching Playwright Test Creation Agent for project {config.project_id}")
        log_callback("INFO", f"Model: {self.model} via TrueFoundry Gateway")

        target_scenarios = config.scenarios
        if not target_scenarios:
            log_callback("WARN", "No test plan scenarios provided or marked for automation.")
            return GeneratorResult(status="success", generated_files=[], automated_scenario_ids=[])

        log_callback("INFO", f"Processing {len(target_scenarios)} scenario(s) marked for automation.")

        # Organize scenarios by category (happy_path, edge_case, error_flow)
        categories = {}
        for sc in target_scenarios:
            cat = sc.get("category", "happy_path")
            categories.setdefault(cat, []).append(sc)

        client = self._get_client()
        workspace_path = Path(config.workspace_dir)
        tests_dir = workspace_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        # Clean stale test spec files to avoid confusing orphan test accumulation
        for old_file in tests_dir.glob("*.spec.py"):
            try:
                old_file.unlink()
                log_callback("INFO", f"Cleaned legacy test file: {old_file.name}")
            except Exception:
                pass
        for old_file in tests_dir.glob("test_*.py"):
            try:
                old_file.unlink()
            except Exception:
                pass

        generated_files: List[GeneratedTestFile] = []
        automated_scenario_ids: List[str] = []
        artifacts_created: List[str] = []

        # Generate explicit test spec file for each scenario
        for idx, sc in enumerate(target_scenarios, 1):
            if is_cancelled():
                return GeneratorResult(status="cancelled")

            sc_title = sc.get("title", f"Scenario {idx}")
            sc_cat = sc.get("category", "happy_path")
            sc_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", sc_title.lower()).strip("_")[:30]
            filename = f"test_{idx:02d}_{sc_cat}_{sc_slug}.spec.py"
            file_path = tests_dir / filename

            log_callback("INFO", f"Generating explicit test spec for Scenario #{idx}: '{sc_title}' [{sc_cat}]...")

            prompt_content = self._build_generation_prompt(config, sc_cat, [sc])
            messages = [
                {"role": "system", "content": self._build_system_prompt(config)},
                {"role": "user", "content": prompt_content},
            ]

            code_content = None
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=GENERATOR_MCP_TOOLS,
                    tool_choice={"type": "function", "function": {"name": "save_test_spec_file"}},
                    extra_headers={
                        "X-TFY-METADATA": "{}",
                        "X-TFY-LOGGING-CONFIG": '{"enabled": true}',
                    },
                )
                message = response.choices[0].message
                if message.tool_calls:
                    call = message.tool_calls[0]
                    args = json.loads(call.function.arguments)
                    code_content = args.get("code_content", "")
            except Exception as e:
                log_callback("WARN", f"LLM generation note for {sc_title}: {e}. Using deterministic code synthesizer.")
                code_content = self._synthesize_code_fallback(config, sc_cat, [sc])

            if not code_content or len(code_content.strip()) < 50:
                code_content = self._synthesize_code_fallback(config, sc_cat, [sc])

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code_content)

            sc_id = sc.get("id")
            if sc_id:
                automated_scenario_ids.append(sc_id)
            artifacts_created.append(str(file_path))

            gen_file = GeneratedTestFile(
                filename=filename,
                relative_path=f"tests/{filename}",
                content=code_content,
                scenario_ids=[sc_id] if sc_id else [],
                test_count=1,
            )
            generated_files.append(gen_file)
            log_callback("INFO", f"Created explicit test spec: tests/{filename}")


        log_callback("INFO", f"Test Creation complete: {len(generated_files)} spec file(s) generated for {len(automated_scenario_ids)} scenario(s).")

        return GeneratorResult(
            status="success",
            generated_files=generated_files,
            automated_scenario_ids=automated_scenario_ids,
            artifacts_created=artifacts_created,
        )


    def _build_system_prompt(self, config: GeneratorConfig) -> str:
        return f"""You are a Senior QA Automation Engineer and Playwright Specialist.
Your job is to convert structured QA test plan scenarios into production-grade, executable Python Playwright test specs.

TARGET APPLICATION:
- URL: {config.target_url}
- Authentication: {config.auth_type}
- Credentials: {json.dumps(config.credentials)}

REQUIREMENTS FOR GENERATED TESTS:
1. Framework: Python Playwright (sync API) with pytest convention `def test_<name>(page: Page)`.
2. Telemetry & Diagnostic Logging:
   - Each test must print or log clear step breadcrumbs in format: `print(f"[STEP {{num}}] {{action}} on '{{target}}'")`
   - Attach network and console listeners to capture backend HTTP errors and unhandled JS exceptions.
   - On assertion or interaction failure, capture a screenshot to `screenshot_path` and log exact failure details.
3. Locators:
   - Use resilient selectors: priority order (1) text or aria-role, (2) name or id, (3) unique CSS.
   - Avoid brittle XPath selectors.
4. Pass / Fail Verification:
   - Derive explicit `expect(...)` assertions from the scenario's `expected_result` and `pass_fail_criteria`.
   - Never write empty or tautological tests.
5. All code must be syntactically valid Python 3, self-contained, and ready to execute.
6. Call `save_test_spec_file` to output the complete file.
"""

    def _build_generation_prompt(self, config: GeneratorConfig, category: str, scenarios: List[Dict[str, Any]]) -> str:
        scenarios_desc = []
        for s in scenarios:
            steps_text = "\n".join([
                f"    Step {st.get('step_number', i+1)}: {st.get('action', '')} on '{st.get('target_element', '')}' -> {st.get('expected_outcome', '')}"
                if isinstance(st, dict) else f"    Step {i+1}: {st}"
                for i, st in enumerate(s.get("steps", []))
            ])
            scenarios_desc.append(f"""
Scenario ID: {s.get('id', 'N/A')}
Title: {s.get('title')}
Priority: {s.get('priority', 'P1')}
Category: {category}
Preconditions: {s.get('preconditions', 'None')}
Description: {s.get('description', '')}
Steps:
{steps_text}
Expected Result: {s.get('expected_result', '')}
Pass/Fail Criteria: {s.get('pass_fail_criteria', '')}
---""")

        return f"""Please generate the Python Playwright test specification file `test_{category}.spec.py` for the following {len(scenarios)} scenarios:
{''.join(scenarios_desc)}

Call `save_test_spec_file` with the complete python code."""

    def _synthesize_code_fallback(
        self,
        config: GeneratorConfig,
        category: str,
        scenarios: List[Dict[str, Any]],
    ) -> str:
        """
        Robust deterministic synthesizer that compiles scenarios into valid Python Playwright tests
        when external LLM gateway is unreachable or offline.
        """
        lines = [
            '"""',
            f'Playwright Test Specification: {category.replace("_", " ").title()}',
            f'Target URL: {config.target_url}',
            'Auto-generated by Aitesty Test Creation Agent',
            '"""',
            'import pytest',
            'import time',
            'from playwright.sync_api import Page, expect',
            '',
            f'TARGET_URL = "{config.target_url}"',
            f'CREDENTIALS = {json.dumps(config.credentials)}',
            '',
        ]

        for s in scenarios:
            title = s.get("title", "Scenario")
            func_name = "test_" + re.sub(r"[^a-zA-Z0-9_]+", "_", title.lower()).strip("_")[:50]
            sc_id = s.get("id", "")
            preconditions = s.get("preconditions", "")
            pass_fail = s.get("pass_fail_criteria", "")
            expected_res = s.get("expected_result", "")
            steps = s.get("steps", [])

            lines.append(f"def {func_name}(page: Page):")
            lines.append('    """')
            lines.append(f'    Scenario: {title}')
            lines.append(f'    Scenario ID: {sc_id}')
            lines.append(f'    Category: {category}')
            if preconditions:
                lines.append(f'    Preconditions: {preconditions}')
            if expected_res:
                lines.append(f'    Expected Result: {expected_res}')
            if pass_fail:
                lines.append(f'    Pass/Fail Criteria: {pass_fail}')
            lines.append('    """')
            lines.append(f'    print("[START TEST] {title}")')
            lines.append('    page.set_default_timeout(10000)')
            lines.append('')

            if not steps:
                lines.append(f'    print("[STEP 1] Navigate to {config.target_url}")')
                lines.append('    response = page.goto(TARGET_URL, wait_until="domcontentloaded")')
                lines.append('    assert response and response.status < 400, f"Page load failed with status {response.status if response else \'None\'}"')
                lines.append('    expect(page.locator("body")).to_be_visible()')
            else:
                for idx, st in enumerate(steps, 1):
                    if isinstance(st, dict):
                        action = (st.get("action") or "").lower()
                        target = st.get("target_element") or ""
                        outcome = st.get("expected_outcome") or ""
                    else:
                        action = str(st).lower()
                        target = ""
                        outcome = ""

                    lines.append(f'    # Step {idx}: {action} on {target or "page"}')
                    lines.append(f'    print(f"[STEP {idx}] {action.upper()} on \'{target}\'")')

                    if "navigate" in action:
                        nav_url = target if target.startswith("http") else f"{config.target_url.rstrip('/')}/{target.lstrip('/')}"
                        lines.append(f'    res = page.goto("{nav_url}", wait_until="domcontentloaded")')
                        lines.append('    assert res and res.status < 400, f"Navigation returned status {res.status if res else \'None\'}"')
                    elif "fill" in action or "type" in action or "enter" in action:
                        selector = target if target else "input"
                        val = outcome if outcome and not outcome.startswith("HTTP") else "test_input_value"
                        lines.append(f'    page.locator("{selector}").first.fill("{val}")')
                    elif "click" in action or "submit" in action:
                        selector = target if target else "button"
                        lines.append(f'    page.locator("{selector}").first.click()')
                        lines.append('    page.wait_for_timeout(400)')
                    elif "assert" in action or "verify" in action:
                        selector = target if target else "body"
                        lines.append(f'    expect(page.locator("{selector}").first).to_be_visible()')
                    else:
                        lines.append('    page.wait_for_timeout(300)')
                    lines.append('')

            # Final verification
            lines.append('    # Verification assertion')
            lines.append('    expect(page.locator("body")).to_be_visible()')
            lines.append(f'    print("[PASSED] {title}")')
            lines.append('')

        return "\n".join(lines)

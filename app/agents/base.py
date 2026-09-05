from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

@dataclass
class ExplorerConfig:
    project_id: str
    target_url: str
    auth_type: str
    credentials: Dict[str, Any]
    scope_instructions: Optional[str]
    workspace_dir: str
    run_id: str
    prd_text: Optional[str] = None
    headless: bool = True
    slow_mo: int = 0

@dataclass
class ScenarioStep:
    step_number: int
    action: str
    target_element: Optional[str] = None
    expected_outcome: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "target_element": self.target_element,
            "expected_outcome": self.expected_outcome,
        }

@dataclass
class DiscoveredScenario:
    title: str
    category: str  # "happy_path" | "edge_case" | "error_flow"
    description: str
    steps: List[Dict[str, Any]]
    expected_result: str
    priority: str = "P1"  # "P0", "P1", "P2", "P3"
    preconditions: Optional[str] = None
    pass_fail_criteria: Optional[str] = None
    status: str = "pending_review"
    source: str = "llm"  # "llm" | "fallback_template"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "priority": self.priority,
            "preconditions": self.preconditions,
            "description": self.description,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "pass_fail_criteria": self.pass_fail_criteria,
            "status": self.status,
            "source": self.source,
        }

@dataclass
class ExplorerResult:
    status: str  # "success" | "failed"
    scenarios: List[DiscoveredScenario] = field(default_factory=list)
    markdown_plan: str = ""
    discovered_routes: List[str] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

class BaseExplorerAgent(ABC):
    """
    Contract for Explorer Sub-Agents.
    Implementations (Stage 1 Mock, Stage 2 Autonomous Playwright Agent)
    must adhere to this signature.
    """

    @abstractmethod
    def explore(
        self,
        config: ExplorerConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ExplorerResult:
        """
        Executes exploration against the target application.
        :param config: ExplorerConfig instance
        :param log_callback: callable(level, message, metadata) to emit real-time logs
        :param cancel_check: callable returning True if cancellation was requested
        :return: ExplorerResult
        """
        pass

@dataclass
class GeneratorConfig:
    project_id: str
    target_url: str
    auth_type: str
    credentials: Dict[str, Any]
    workspace_dir: str
    run_id: str
    scenarios: List[Dict[str, Any]] = field(default_factory=list)
    scope_instructions: Optional[str] = None
    prd_text: Optional[str] = None

@dataclass
class GeneratedTestFile:
    filename: str
    relative_path: str
    content: str
    scenario_ids: List[str] = field(default_factory=list)
    test_count: int = 1
    subtest_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filename": self.filename,
            "relative_path": self.relative_path,
            "scenario_ids": self.scenario_ids,
            "test_count": self.test_count,
            "subtest_count": self.subtest_count,
        }

@dataclass
class GeneratorResult:
    status: str  # "success" | "failed" | "cancelled"
    generated_files: List[GeneratedTestFile] = field(default_factory=list)
    automated_scenario_ids: List[str] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

class BaseGeneratorAgent(ABC):
    """
    Contract for Test Creation (Generator) Sub-Agents.
    Converts reviewed & marked test plan scenarios into executable Playwright tests.
    """

    @abstractmethod
    def generate(
        self,
        config: GeneratorConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> GeneratorResult:
        """
        Synthesizes executable tests for marked scenarios.
        :param config: GeneratorConfig instance
        :param log_callback: callable(level, message, metadata) to emit real-time logs
        :param cancel_check: callable returning True if cancellation requested
        :return: GeneratorResult
        """
        pass

@dataclass
class HealingConfig:
    project_id: str
    target_url: str
    workspace_dir: str
    run_ids: List[str]                  # Selected run IDs to analyze
    scenarios: List[Dict[str, Any]] = field(default_factory=list) # Active scenarios from test plan
    run_results: List[Dict[str, Any]] = field(default_factory=list) # Parsed results from each run
    prd_text: Optional[str] = None
    scope_instructions: Optional[str] = None

@dataclass
class FailedCaseAnalysis:
    test_name: str
    scenario_id: Optional[str]
    scenario_title: Optional[str]
    file_name: Optional[str]
    status: str                         # "failed"
    failure_origin: str                 # "PRODUCT_DEFECT" | "AUTOMATION_FAILURE" | "UNKNOWN"
    verdict: str                        # "NEEDS_FIX" | "INVALID_TESTCASE" | "REAL_BUG"
    summary: str
    root_cause: str
    notes_for_planner: str              # Actionable notes for the QA planner
    notes_for_generator: str            # Guidance for test generation/patching
    suggested_fix: Optional[str] = None
    suggested_selectors: List[str] = field(default_factory=list)
    confidence: float = 0.90
    raw_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "scenario_id": self.scenario_id,
            "scenario_title": self.scenario_title,
            "file_name": self.file_name,
            "status": self.status,
            "failure_origin": self.failure_origin,
            "verdict": self.verdict,
            "summary": self.summary,
            "root_cause": self.root_cause,
            "notes_for_planner": self.notes_for_planner,
            "notes_for_generator": self.notes_for_generator,
            "suggested_fix": self.suggested_fix,
            "suggested_selectors": self.suggested_selectors,
            "confidence": self.confidence,
            "raw_error": self.raw_error,
        }

@dataclass
class HealingResult:
    status: str                         # "success" | "failed" | "cancelled"
    analyzed_runs: List[str] = field(default_factory=list)
    failed_cases_analyzed: int = 0
    app_defects_count: int = 0
    automation_failures_count: int = 0
    healed_tests_count: int = 0
    invalid_tests_count: int = 0
    analyses: List[FailedCaseAnalysis] = field(default_factory=list)
    artifacts_created: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "analyzed_runs": self.analyzed_runs,
            "failed_cases_analyzed": self.failed_cases_analyzed,
            "app_defects_count": self.app_defects_count,
            "automation_failures_count": self.automation_failures_count,
            "healed_tests_count": self.healed_tests_count,
            "invalid_tests_count": self.invalid_tests_count,
            "analyses": [a.to_dict() for a in self.analyses],
            "artifacts_created": self.artifacts_created,
            "error_message": self.error_message,
        }

class BaseHealingAgent(ABC):
    """
    Contract for Test Results Analysis & Healing Sub-Agents.
    Examines failed test runs, performs failure attribution (App Defect vs Automation Failure),
    decides whether the testcase needs healing vs is invalid, and generates notes for
    the planning and generator agents.
    """

    @abstractmethod
    def analyze_and_heal(
        self,
        config: HealingConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> HealingResult:
        pass


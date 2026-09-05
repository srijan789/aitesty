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
<<<<<<< HEAD
    # Planner re-plan loop support (all optional/defaulted -> backward compatible)
    product_requirements: Optional[str] = None
    coverage_feedback: List[str] = field(default_factory=list)
    attempt_number: int = 1
=======
    prd_text: Optional[str] = None
<<<<<<< HEAD
>>>>>>> 145374c (Added the Exploratory + test planning agent)
=======
    # Planner re-plan loop support (all optional/defaulted -> backward compatible)
    coverage_feedback: List[str] = field(default_factory=list)
    attempt_number: int = 1
>>>>>>> 561a6cf (add an orchestrator at higher level)

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


# ---------------------------------------------------------------------------
# Generator Sub-Agent Contract
# ---------------------------------------------------------------------------

@dataclass
class GeneratorConfig:
    project_id: str
    target_url: str
    auth_type: str
    credentials: Dict[str, Any]
    workspace_dir: str
    run_id: str
    plan: Dict[str, Any]  # the current TestPlan dict (scenarios + discovered_routes)


@dataclass
class GeneratedTestFile:
    relative_path: str  # relative to the project workspace, e.g. "tests/test_auth_flow.spec.py"
    content: str
    covers_test_case_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "covers_test_case_ids": self.covers_test_case_ids,
        }


@dataclass
class GeneratorResult:
    status: str  # "success" | "failed"
    files: List[GeneratedTestFile] = field(default_factory=list)
    validation_report: Dict[str, Any] = field(default_factory=dict)  # per-scenario selector/assertion validation notes
    error_message: Optional[str] = None


class BaseGeneratorAgent(ABC):
    """
    Contract for Generator Sub-Agents. Converts a test plan into executable test file contents
    with live selector/assertion validation against the target application. Implementations must
    NOT write to disk themselves -- the orchestrator persists `files` via WorkspaceManager so path
    sanitization stays centralized.
    """

    @abstractmethod
    def generate(
        self,
        config: GeneratorConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> GeneratorResult:
        """
        Produces executable test files from a structured test plan.
        :param config: GeneratorConfig instance
        :param log_callback: callable(level, message, metadata) to emit real-time logs
        :param cancel_check: callable returning True if cancellation was requested
        :return: GeneratorResult
        """
        pass


# ---------------------------------------------------------------------------
# Healer Sub-Agent Contract
# ---------------------------------------------------------------------------

@dataclass
class HealerConfig:
    project_id: str
    workspace_dir: str
    run_id: str
    test_case_id: str
    script_path: Optional[str]
    failure_output: str
    attempt_number: int = 1
    max_attempts: int = 3


@dataclass
class HealerResult:
    status: str  # "resolved" | "unresolved" | "escalated"
    classification: str = "unknown"  # "script_bug" | "app_defect" | "unknown"
    action_taken: Optional[str] = None  # "repaired_script" | "recommended_fix" | "escalated"
    updated_script_content: Optional[str] = None
    recommendation_text: Optional[str] = None
    confidence: float = 0.0
    error_message: Optional[str] = None


class BaseHealerAgent(ABC):
    """
    Contract for Healer Sub-Agents. Replays a failing test and classifies the failure as a
    broken test script (a stale/changed locator, timing, or workflow step) vs a genuine
    application defect. For a script bug, it repairs the locator/workflow directly. For a
    suspected application defect it never modifies application code -- it only reports the
    classification and a recommended fix for a human to review. Implementations must NOT write
    to disk themselves -- the orchestrator persists `updated_script_content` via WorkspaceManager
    so path sanitization stays centralized.
    """

    @abstractmethod
    def heal(
        self,
        config: HealerConfig,
        log_callback: Callable[[str, str, Optional[Dict[str, Any]]], None],
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> HealerResult:
        """
        Attempts to diagnose and repair a single failing test.
        :param config: HealerConfig instance
        :param log_callback: callable(level, message, metadata) to emit real-time logs
        :param cancel_check: callable returning True if cancellation was requested
        :return: HealerResult
        """
        pass

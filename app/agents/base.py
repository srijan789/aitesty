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
    suggested_spec_filename: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "suggested_spec_filename": self.suggested_spec_filename,
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

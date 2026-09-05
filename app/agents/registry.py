from typing import Dict, Type
from app.agents.base import BaseExplorerAgent
from app.agents.mock_explorer import MockExplorerAgent

_EXPLORER_REGISTRY: Dict[str, Type[BaseExplorerAgent]] = {
    "mock": MockExplorerAgent,
}

def register_explorer_agent(name: str, agent_cls: Type[BaseExplorerAgent]):
    _EXPLORER_REGISTRY[name.lower()] = agent_cls

def get_explorer_agent(name: str = "mock") -> BaseExplorerAgent:
    agent_cls = _EXPLORER_REGISTRY.get(name.lower(), MockExplorerAgent)
    return agent_cls()

from typing import Dict, Type
from app.agents.base import BaseExplorerAgent
from app.agents.mock_explorer import MockExplorerAgent
from app.agents.playwright_explorer import PlaywrightExplorerAgent

_EXPLORER_REGISTRY: Dict[str, Type[BaseExplorerAgent]] = {
    "playwright": PlaywrightExplorerAgent,
    "mock": MockExplorerAgent,
}

def register_explorer_agent(name: str, agent_cls: Type[BaseExplorerAgent]):
    _EXPLORER_REGISTRY[name.lower()] = agent_cls

def get_explorer_agent(name: str = "playwright") -> BaseExplorerAgent:
    agent_cls = _EXPLORER_REGISTRY.get(name.lower(), PlaywrightExplorerAgent)
    return agent_cls()

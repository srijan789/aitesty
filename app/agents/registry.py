from typing import Dict, Type
from app.agents.base import BaseExplorerAgent, BaseGeneratorAgent
from app.agents.mock_explorer import MockExplorerAgent
from app.agents.playwright_explorer import PlaywrightExplorerAgent
from app.agents.mock_generator import MockGeneratorAgent
from app.agents.playwright_generator import PlaywrightGeneratorAgent

_EXPLORER_REGISTRY: Dict[str, Type[BaseExplorerAgent]] = {
    "playwright": PlaywrightExplorerAgent,
    "mock": MockExplorerAgent,
}

_GENERATOR_REGISTRY: Dict[str, Type[BaseGeneratorAgent]] = {
    "playwright": PlaywrightGeneratorAgent,
    "mock": MockGeneratorAgent,
}

def register_explorer_agent(name: str, agent_cls: Type[BaseExplorerAgent]):
    _EXPLORER_REGISTRY[name.lower()] = agent_cls

def get_explorer_agent(name: str = "playwright") -> BaseExplorerAgent:
    agent_cls = _EXPLORER_REGISTRY.get(name.lower(), PlaywrightExplorerAgent)
    return agent_cls()

def register_generator_agent(name: str, agent_cls: Type[BaseGeneratorAgent]):
    _GENERATOR_REGISTRY[name.lower()] = agent_cls

def get_generator_agent(name: str = "playwright") -> BaseGeneratorAgent:
    agent_cls = _GENERATOR_REGISTRY.get(name.lower(), PlaywrightGeneratorAgent)
    return agent_cls()


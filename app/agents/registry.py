from typing import Dict, Type
from app.agents.base import BaseExplorerAgent, BaseGeneratorAgent, BaseHealerAgent
from app.agents.mock_explorer import MockExplorerAgent
<<<<<<< HEAD
from app.agents.mock_generator import MockGeneratorAgent
from app.agents.mock_healer import MockHealerAgent
=======
from app.agents.playwright_explorer import PlaywrightExplorerAgent
>>>>>>> 145374c (Added the Exploratory + test planning agent)

_EXPLORER_REGISTRY: Dict[str, Type[BaseExplorerAgent]] = {
    "playwright": PlaywrightExplorerAgent,
    "mock": MockExplorerAgent,
}

_GENERATOR_REGISTRY: Dict[str, Type[BaseGeneratorAgent]] = {
    "mock": MockGeneratorAgent,
}

_HEALER_REGISTRY: Dict[str, Type[BaseHealerAgent]] = {
    "mock": MockHealerAgent,
}


def register_explorer_agent(name: str, agent_cls: Type[BaseExplorerAgent]):
    _EXPLORER_REGISTRY[name.lower()] = agent_cls

<<<<<<< HEAD

def register_generator_agent(name: str, agent_cls: Type[BaseGeneratorAgent]):
    _GENERATOR_REGISTRY[name.lower()] = agent_cls


def register_healer_agent(name: str, agent_cls: Type[BaseHealerAgent]):
    _HEALER_REGISTRY[name.lower()] = agent_cls


def get_explorer_agent(name: str = "mock") -> BaseExplorerAgent:
    agent_cls = _EXPLORER_REGISTRY.get(name.lower(), MockExplorerAgent)
=======
def get_explorer_agent(name: str = "playwright") -> BaseExplorerAgent:
    agent_cls = _EXPLORER_REGISTRY.get(name.lower(), PlaywrightExplorerAgent)
>>>>>>> 145374c (Added the Exploratory + test planning agent)
    return agent_cls()


def get_generator_agent(name: str = "mock") -> BaseGeneratorAgent:
    agent_cls = _GENERATOR_REGISTRY.get(name.lower(), MockGeneratorAgent)
    return agent_cls()


def get_healer_agent(name: str = "mock") -> BaseHealerAgent:
    agent_cls = _HEALER_REGISTRY.get(name.lower(), MockHealerAgent)
    return agent_cls()

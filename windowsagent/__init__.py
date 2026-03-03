"""
WindowsAgent — Open-source AI agent for Windows desktop automation.

Uses Windows UI Automation API as primary element targeting, with a vision model
fallback for legacy or custom-rendered applications.

Quick start:
    from windowsagent import Agent, Config

    agent = Agent()
    state = agent.observe("Notepad")
    result = agent.act("Notepad", action="type", target="Text Editor", params={"text": "Hello"})

For full documentation, see: https://github.com/ibraheem4/windowsagent
"""

from windowsagent.agent import Agent
from windowsagent.config import Config, load_config

__version__ = "0.1.0"
__all__ = ["Agent", "Config", "load_config", "__version__"]

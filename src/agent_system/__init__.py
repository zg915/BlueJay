"""
Agents package for OpenAI Agents SDK
"""

def get_main_agent():
    """Get the main triage agent"""
    from .orchestration import get_main_agent as _get_main_agent
    return _get_main_agent()

from .agents import *

__all__ = [
    "get_main_agent",
    "Agent",
    "handoff",
    "function_tool",
    "CertificationAgent",
    "AnswerAgent"
] 
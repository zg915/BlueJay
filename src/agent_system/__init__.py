"""
Agents package for OpenAI Agents SDK
"""

# Only keep the functions that are actually used
def get_main_agent():
    """Get the main triage agent"""
    from .orchestration import get_main_agent as _get_main_agent
    return _get_main_agent()

__all__ = [
    "get_main_agent"
] 
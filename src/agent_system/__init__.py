"""
Agents package for OpenAI Agents SDK
"""

# Lazy imports to avoid circular dependencies
def get_main_agent():
    """Get the main triage agent"""
    from .orchestration import get_main_agent as _get_main_agent
    return _get_main_agent()

def get_agent(agent_name: str):
    """Get an agent by name"""
    from .specialized_agents import get_agent as _get_agent
    return _get_agent(agent_name)

def get_all_agents():
    """Get all agents"""
    from .specialized_agents import get_all_agents as _get_all_agents
    return _get_all_agents()

def get_agent_info():
    """Get information about all agents"""
    from .specialized_agents import get_agent_info as _get_agent_info
    return _get_agent_info()

def get_tools(*tool_names: str):
    """Get tools by name from registry"""
    from .tools_registry import get_tools as _get_tools
    return _get_tools(*tool_names)

def get_all_tools():
    """Get all tools from registry"""
    from .tools_registry import get_all_tools as _get_all_tools
    return _get_all_tools()

def get_tool_names():
    """Get all tool names from registry"""
    from .tools_registry import get_tool_names as _get_tool_names
    return _get_tool_names()

def register_tool(name: str, tool_func):
    """Register a new tool in the registry"""
    from .tools_registry import register_tool as _register_tool
    return _register_tool(name, tool_func)

def unregister_tool(name: str):
    """Remove a tool from the registry"""
    from .tools_registry import unregister_tool as _unregister_tool
    return _unregister_tool(name)

def tool_exists(name: str):
    """Check if a tool exists in the registry"""
    from .tools_registry import tool_exists as _tool_exists
    return _tool_exists(name)

def get_tool_info():
    """Get information about all tools in the registry"""
    from .tools_registry import get_tool_info as _get_tool_info
    return _get_tool_info()

def get_tool_set(set_name: str):
    """Get a predefined set of tools"""
    from .tools_registry import get_tool_set as _get_tool_set
    return _get_tool_set(set_name)

def add_tool_set(set_name: str, tool_names):
    """Add a new predefined tool set"""
    from .tools_registry import add_tool_set as _add_tool_set
    return _add_tool_set(set_name, tool_names)

def check_tool_registry_health():
    """Check the health of the tool registry"""
    from .tools_registry import check_tool_registry_health as _check_tool_registry_health
    return _check_tool_registry_health()

__all__ = [
    "get_main_agent",
    "get_agent",
    "get_all_agents",
    "get_agent_info",
    "get_tools",
    "get_all_tools",
    "get_tool_names",
    "register_tool",
    "unregister_tool",
    "tool_exists",
    "get_tool_info",
    "get_tool_set",
    "add_tool_set",
    "check_tool_registry_health"
] 
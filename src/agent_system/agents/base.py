"""
Base agent class and agent framework utilities
"""
from agents import Agent as SDKAgent, handoff

def function_tool(func):
    # Decorator stub for function tools
    return func

# Use the SDK's Agent as the base class for all agents
class Agent(SDKAgent):
    pass 
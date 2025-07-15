"""
CertificationWorkflowAgent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import handle_certification_list_workflow

class CertificationWorkflowAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Certification workflow agent",
            instructions=(
                "You are a certification workflow agent.\n"
                "You MUST always use the tool: handle_certification_list_workflow.\n"
                "NEVER respond directly to the user. If you cannot use the tool, return an error.\n"
                "Always return structured data that can be processed by the main system."
            ),
            tools=[handle_certification_list_workflow],
            model_settings=ModelSettings(tool_choice="handle_certification_list_workflow"),
            tool_use_behavior="stop_on_first_tool"
        )
        self.orchestrator = orchestrator 
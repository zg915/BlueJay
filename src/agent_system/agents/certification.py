"""
CertificationAgent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import search_relevant_certification
from src.config.prompts import CERTIFICATION_AGENT_INSTRUCTION

class CertificationAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Certification workflow agent",
            #TODO: edit the description and instruction
            handoff_description = "",
            instructions=(
                "You are a certification workflow agent.\n"
                "You MUST always use the tool: search_relevant_certification.\n"
                "After receiving the list of certifications, deduplicate them using your own reasoning—do not call any deduplication tool.\n"
                "Only return unique certifications, grouped by their official name.\n"
                "Stream each unique certification as a separate response.\n"
                "NEVER respond directly to the user. If you cannot use the tool, return an error.\n"
                "Always return structured data that can be processed by the main system."
            ),
            tools=[search_relevant_certification],
            model_settings=ModelSettings(tool_choice="search_relevant_certification")
        )
        self.orchestrator = orchestrator 
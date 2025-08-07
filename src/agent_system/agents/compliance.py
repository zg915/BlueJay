"""
ComplianceAgent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import gather_compliance, web_search, prepare_flashcard
from src.config.prompts import COMPLIANCE_AGENT_INSTRUCTION, COMPLIANCE_AGENT_DESCRIPTION

class ComplianceAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Compliance Agent",
            model="gpt-4.1", 
            handoff_description = COMPLIANCE_AGENT_DESCRIPTION,
            instructions=COMPLIANCE_AGENT_INSTRUCTION,
            tools=[gather_compliance, prepare_flashcard, web_search],

        ) 
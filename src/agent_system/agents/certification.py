"""
CertificationAgent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import search_relevant_certification
from src.config.prompts import CERTIFICATION_AGENT_INSTRUCTION, CERTIFICATION_AGENT_DESCRIPTION
from pydantic import BaseModel, Field
from typing import List
from src.config.output_structure import Certifications_Structure

class CertificationAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Certification Agent",
            model="gpt-4.1", 
            handoff_description = CERTIFICATION_AGENT_DESCRIPTION,
            instructions=CERTIFICATION_AGENT_INSTRUCTION,
            tools=[search_relevant_certification],
            model_settings=ModelSettings(tool_choice="search_relevant_certification"),
            output_type=Certifications_Structure
        )
        self.orchestrator = orchestrator 
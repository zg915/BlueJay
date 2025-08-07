"""
ComplianceDiscoveryAgent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import compliance_lookup, web_search
from src.config.prompts import COMPLIANCE_DISCOVERY_AGENT_INSTRUCTION
from pydantic import BaseModel, Field
from src.config.schemas import ComplianceList_Structure

class ComplianceDiscoveryAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Compliance Discovery Agent",
            model="gpt-4.1", 
            instructions=COMPLIANCE_DISCOVERY_AGENT_INSTRUCTION,
            tools=[compliance_lookup, web_search],
            output_type=ComplianceList_Structure
        ) 
"""
Compliance Ingestion Agent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import compliance_lookup, web_search, compliance_save
from src.config.prompts import COMPLIANCE_INGESTION_AGENT_INSTRUCTION
from pydantic import BaseModel, Field
from typing import Optional


class ComplianceIngestionAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Compliance Ingestion Agent",
            instructions=COMPLIANCE_INGESTION_AGENT_INSTRUCTION,
            tools=[compliance_lookup, web_search, compliance_save]
        ) 
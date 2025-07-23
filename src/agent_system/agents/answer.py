"""
AnswerAgent definition
"""
from .base import Agent
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.prompts import ANSWER_AGENT_INSTRUCTION, ANSWER_AGENT_DESCRIPTION
from agents import ModelSettings
from src.agent_system.tools.core import compliance_research, web_search, prepare_flashcard
from src.config.output_structure import Answer_Structure
from pydantic import BaseModel
from typing import Optional

class AnswerAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Answer Agent",
            model="gpt-4o",
            handoff_description=ANSWER_AGENT_DESCRIPTION,
            instructions=ANSWER_AGENT_INSTRUCTION,
            tools=[prepare_flashcard, compliance_research, web_search],
            output_type=Answer_Structure
        )
        self.orchestrator = orchestrator
"""
AnswerAgent definition
"""
from .base import Agent
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.prompts import ANSWER_AGENT_INSTRUCTION, ANSWER_AGENT_DESCRIPTION
from agents import ModelSettings
from src.agent_system.tools.core import handle_general_research_workflow

class AnswerAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Answer Agent",
            model="gpt-4o",
            handoff_description=ANSWER_AGENT_DESCRIPTION,
            instructions=ANSWER_AGENT_INSTRUCTION,
            tools=[handle_general_research_workflow],
            model_settings=ModelSettings(tool_choice="handle_general_research_workflow")
        )
        self.orchestrator = orchestrator
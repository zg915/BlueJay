"""
Guide Agent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import web_search
from src.config.prompts import GUIDE_AGENT_INSTRUCTION, GUIDE_AGENT_DESCRIPTION
from pydantic import BaseModel, Field
from typing import Optional
from src.config.schemas import Flashcard_Structure, GuideOutput

#TODO: change into a better name
class GuideAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Guide Agent",
            handoff_description = GUIDE_AGENT_DESCRIPTION,
            instructions=GUIDE_AGENT_INSTRUCTION,
            tools=[web_search],
            output_type=GuideOutput
        ) 
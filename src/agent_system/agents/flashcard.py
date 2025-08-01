"""
Flash Card Agent definition
"""
from agents import Agent, ModelSettings
from src.agent_system.tools.core import compliance_lookup, flashcard_web_search
from src.config.prompts import FLASHCARD_AGENT_INSTRUCTION, FLASHCARD_AGENT_DESCRIPTION
from pydantic import BaseModel, Field
from typing import Optional
from src.config.schemas import Flashcard_Structure


class FlashcardAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Flash Card Agent",
            handoff_description = FLASHCARD_AGENT_DESCRIPTION,
            instructions=FLASHCARD_AGENT_INSTRUCTION,
            tools=[compliance_lookup, flashcard_web_search],
            output_type=Flashcard_Structure
        ) 
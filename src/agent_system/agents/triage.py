"""
TriageAgent definition - Routes user queries to appropriate specialized agents
"""
from agents import Agent, handoff
from src.config.prompts import TRIAGE_AGENT_INSTRUCTION
from src.config.schemas import Reason_Structure

class TriageAgent(Agent):
    def __init__(self, certification_agent, answer_agent):
        def _print_reason(context, input):
            print("reason of choosing the workflow: ", input)
            
        super().__init__(
            name="Triage agent",
            model="gpt-4o",
            instructions=TRIAGE_AGENT_INSTRUCTION,
            handoffs=[
                handoff(certification_agent,
                        input_type=Reason_Structure,
                        on_handoff=_print_reason),
                handoff(answer_agent,
                        input_type=Reason_Structure,
                        on_handoff=_print_reason)
            ]
        )
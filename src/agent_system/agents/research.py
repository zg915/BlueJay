"""
ResearchWorkflowAgent definition
"""
from .base import Agent
from sqlalchemy.ext.asyncio import AsyncSession
from agents import ModelSettings
from src.agent_system.tools.core import handle_general_research_workflow

class ResearchWorkflowAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Research workflow agent",
            instructions=(
                "You are a research workflow agent.\n"
                "You MUST always use the tool: handle_general_research_workflow.\n"
                "After receiving the list of research results, deduplicate them using your own reasoning—do not call any deduplication tool.\n"
                "Only return unique results, grouped by their official name or title.\n"
                "Return the results as a simple JSON array of research objects, each with these fields:\n"
                "- title\n"
                "- content\n"
                "- source\n"
                "- relevance_score\n"
                "NEVER respond directly to the user. If you cannot use the tool, return an error.\n"
                "Always return structured data that can be processed by the main system."
            ),
            tools=[handle_general_research_workflow],
            model_settings=ModelSettings(tool_choice="handle_general_research_workflow")
        )
        self.orchestrator = orchestrator

    # The run method is not needed in tool-only mode
    # async def run(self, enhanced_query: str, context: dict = None, db: AsyncSession = None):
    #     """Execute research workflow and return results"""
    #     print(f"🔧 ResearchWorkflowAgent.run() called with query: {enhanced_query}")
    #     print(f"🔧 Context: {context}")
    #     print(f"🔧 DB: {db}")
    #     try:
    #         if isinstance(context, str):
    #             try:
    #                 import json
    #                 context = json.loads(context)
    #             except:
    #                 context = {}
    #         if db is None:
    #             print("⚠️ No database session provided, using mock context")
    #             context = context or {}
    #         result = await self.orchestrator.handle_general_research_workflow(enhanced_query, context, db)
    #         print(f"✅ ResearchWorkflowAgent returning: {len(result) if isinstance(result, list) else 'non-list'} results")
    #         return result
    #     except Exception as e:
    #         print(f"❌ ResearchWorkflowAgent error: {e}")
    #         import traceback
    #         print(f"🔍 Full traceback: {traceback.format_exc()}")
    #         return f"Error in research workflow: {str(e)}" 
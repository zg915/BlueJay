"""
ResearchWorkflowAgent definition
"""
from .base import Agent
from sqlalchemy.ext.asyncio import AsyncSession

class ResearchWorkflowAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Research workflow agent",
            instructions="""You are a research workflow agent. \
Your job is to process general research queries and return comprehensive information.\
When called, you will receive an enhanced query and should return detailed research results.\
Always return structured data that can be processed by the main system."""
        )
        self.orchestrator = orchestrator

    async def run(self, enhanced_query: str, context: dict = None, db: AsyncSession = None):
        """Execute research workflow and return results"""
        print(f"🔧 ResearchWorkflowAgent.run() called with query: {enhanced_query}")
        print(f"🔧 Context: {context}")
        print(f"🔧 DB: {db}")
        try:
            if isinstance(context, str):
                try:
                    import json
                    context = json.loads(context)
                except:
                    context = {}
            if db is None:
                print("⚠️ No database session provided, using mock context")
                context = context or {}
            result = await self.orchestrator.handle_general_research_workflow(enhanced_query, context, db)
            print(f"✅ ResearchWorkflowAgent returning: {len(result) if isinstance(result, list) else 'non-list'} results")
            return result
        except Exception as e:
            print(f"❌ ResearchWorkflowAgent error: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            return f"Error in research workflow: {str(e)}" 
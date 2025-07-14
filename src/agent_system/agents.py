from agents import Agent, handoff, function_tool
from src.agent_system.tools import get_recent_context
from src.config.prompts import (
    TRIAGE_AGENT_PROMPT,
    LIST_GENERATION_AGENT_PROMPT,
    RESEARCH_AGENT_PROMPT,
    DIRECT_RESPONSE_AGENT_PROMPT
)

class CertificationWorkflowAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Certification workflow agent",
            instructions=""
        )
        self.orchestrator = orchestrator
    #TODO: print and check if the enhanced_query, context are correct
    async def run(self, enhanced_query, context=None, db=None):
        """Execute certification workflow and return results"""
        print(f"🔧 CertificationWorkflowAgent.run() called with query: {enhanced_query}")
        print(f"🔧 Context: {context}")
        print(f"🔧 DB: {db}")
        
        try:
            # If context is a string, parse it as JSON
            if isinstance(context, str):
                try:
                    import json
                    context = json.loads(context)
                except:
                    context = {}
            
            #TODO: do we really need to worry this part?
            # If db is not provided, we'll need to handle this
            if db is None:
                print("⚠️ No database session provided, using mock context")
                context = context or {}
            
            result = await self.orchestrator.handle_certification_list_workflow(enhanced_query, context, db)
            print(f"✅ CertificationWorkflowAgent returning: {len(result) if isinstance(result, list) else 'non-list'} results")
            return result
        except Exception as e:
            print(f"❌ CertificationWorkflowAgent error: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            return f"Error in certification workflow: {str(e)}"

class ResearchWorkflowAgent(Agent):
    def __init__(self, orchestrator):
        super().__init__(
            name="Research workflow agent",
            instructions="""You are a research workflow agent. 
Your job is to process general research queries and return comprehensive information.
When called, you will receive an enhanced query and should return detailed research results.
Always return structured data that can be processed by the main system."""
        )
        self.orchestrator = orchestrator

    async def run(self, enhanced_query, context=None, db=None):
        """Execute research workflow and return results"""
        print(f"🔧 ResearchWorkflowAgent.run() called with query: {enhanced_query}")
        print(f"🔧 Context: {context}")
        print(f"🔧 DB: {db}")
        
        try:
            # If context is a string, parse it as JSON
            if isinstance(context, str):
                try:
                    import json
                    context = json.loads(context)
                except:
                    context = {}
            
            # If db is not provided, we'll need to handle this
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
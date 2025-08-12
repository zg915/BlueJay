"""
Operations for research and search workflows
"""
import time
from agents import Runner
from langfuse import get_client


async def web_search(query: str, use_domain: bool = False):
    """RAG API + Domain Search: Get domain metadata and search with domain filter"""
    from src.services.knowledgebase_service import kb_domain_lookup
    from src.services.perplexity_service import perplexity_search
    try:
        if use_domain:
            domains = await kb_domain_lookup(query)
        else:
            domains = None

        result = await perplexity_search(query, domains)
        return result
        
    except Exception as e:
        print(f"❌ domain web search failed: {e}")
        return {}

async def run_flashcard_agent(compliance_name: str, context: str = None, language: str = "en"):
    """Generate flashcard for a compliance using FlashcardAgent"""
    from ..agents import FlashcardAgent
    
    agent = FlashcardAgent()

    result = await Runner.run(
        agent,
        input=str({"compliance_name": compliance_name, "context": context, "language": language}),
    )

    # Convert Pydantic model to JSON string for better parsing in streaming
    final_output = result.final_output
    if hasattr(final_output, 'model_dump_json'):
        # Pydantic v2 method
        return final_output.model_dump_json()
    elif hasattr(final_output, 'json'):
        # Pydantic v1 method
        return final_output.json()
    else:
        # Fallback to regular string conversion
        return str(final_output)

async def background_run_compliance_ingestion(query: str):
    """
    Run background compliance ingestion agent
    
    Args:
        query: Search query for compliance artifacts (typically certification name)
    
    Returns:
        dict: Results with status, result, and execution time
    """
    import time
    from ..agents.background_compliance_ingestion import ComplianceIngestionAgent
    
    start_time = time.time()
    
    try:
        print(f"🔄 Starting background compliance agent for: {query[:30]}")
        
        agent = ComplianceIngestionAgent()
        langfuse = get_client()
        with langfuse.start_as_current_span(name="Background Compliance Ingestion") as span:

            result = await Runner.run(agent, input=query)
                            # Update trace once with all information
            span.update_trace(
                input=query,
                output=result.final_output,
                tags=["Background", "Update Compliance Artifact"]
            )
        
        execution_time = time.time() - start_time
        print(f"✅ Background compliance agent completed for: {query[:30]} in {execution_time:.2f}s")
        
        return {
            "status": "success",
            "query": query,
            "result": str(result.final_output),
            "execution_time": f"{execution_time:.2f}s"
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"⚠️ Background compliance agent failed for {query[:30]}: {e} (took {execution_time:.2f}s)")
        
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "error_type": type(e).__name__,
            "execution_time": f"{execution_time:.2f}s"
        }
    
async def run_compliance_discovery_agent(query: str):
    """Run compliance discovery agent"""
    from ..agents.compliance_discovery import ComplianceDiscoveryAgent
    
    agent = ComplianceDiscoveryAgent()

    result = await Runner.run(
        agent,
        input=query,
    )

    # Extract the list from the structured output
    if hasattr(result.final_output, 'response'):
        return result.final_output.response
    else:
        return result.final_output
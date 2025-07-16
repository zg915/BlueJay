from agents import function_tool
from typing import Optional
import json
import ast

# Global orchestrator placeholder (set this from your app entrypoint)
global_orchestrator = None

def set_global_orchestrator(orchestrator):
    """Set the global orchestrator for tools to access"""
    global global_orchestrator
    global_orchestrator = orchestrator
    return True

@function_tool
def set_certification_workflow_orchestrator(orchestrator):
    global global_orchestrator
    global_orchestrator = orchestrator
    return True

def safe_parse_context(context_json):
    print(f"[DEBUG] Raw context_json: {context_json!r}")
    if not context_json:
        return None
    try:
        return json.loads(context_json)
    except Exception:
        try:
            import ast
            return ast.literal_eval(context_json)
        except Exception:
            # Try string replacement as last resort
            fixed = (
                context_json
                .replace('None', 'null')
                .replace('True', 'true')
                .replace('False', 'false')
                .replace("'", '"')
            )
            try:
                return json.loads(fixed)
            except Exception:
                raise ValueError("Context is not valid JSON or Python dict string")

@function_tool
async def handle_certification_list_workflow(enhanced_query: str, context_json: Optional[str] = None):
    #TODO: alt2er the tool description
    """
    Specialized workflow for certification list requests.
    Includes internal DB lookup, web search, fuzzy deduplication, and vector caching.
    """
    print(f"📋 Starting certification list workflow for: {enhanced_query}")
    context = safe_parse_context(context_json)
    if global_orchestrator is None:
        raise RuntimeError("Orchestrator not set. Call set_certification_workflow_orchestrator first.")
    db = getattr(global_orchestrator, 'db', None)
    return await global_orchestrator.handle_certification_list_workflow(enhanced_query, context, db)

@function_tool
async def handle_general_research_workflow(enhanced_query: str, context_json: Optional[str] = None):
    """
    Specialized workflow for general research requests.
    """
    print(f"🔬 Starting general research workflow for: {enhanced_query}")
    context = safe_parse_context(context_json)
    if global_orchestrator is None:
        raise RuntimeError("Orchestrator not set. Call set_global_orchestrator first.")
    db = getattr(global_orchestrator, 'db', None)
    return await global_orchestrator.handle_general_research_workflow(enhanced_query, context, db)

@function_tool
def get_recent_context(session_id: str):
    """
    Tool stub for agent use. Does not fetch from DB directly.
    """
    return {}

@function_tool
def call_rag_api(text: str, dataset_id: str = None, limit: int = 2500, similarity: int = 0, search_mode: str = "embedding", using_re_rank: bool = False):
    from src.agent_system.internal import _call_rag_api_impl
    return _call_rag_api_impl(text, dataset_id, limit, similarity, search_mode, using_re_rank)

@function_tool
def generate_search_queries(enhanced_query: str, num_queries: int = 4):
    from . import _generate_search_queries_impl
    return _generate_search_queries_impl(enhanced_query, num_queries)

@function_tool
def map_queries_to_websites(queries: list[str], domain_metadata: str):
    from . import _map_queries_to_websites_impl
    return _map_queries_to_websites_impl(queries, domain_metadata)

@function_tool
def perplexity_domain_search(query: str, domains: list = None):
    from src.agent_system.internal import _perplexity_domain_search_impl
    return _perplexity_domain_search_impl(query, domains)

@function_tool
def create_parallel_queries(queries: list[str]):
    return queries

@function_tool
async def run_parallel_queries(query_funcs: list[str]):
    import asyncio
    results = await asyncio.gather(*[func() for func in query_funcs])
    return results

@function_tool
def synthesize_results(results: list[str]):
    return "\n".join(str(r) for r in results) 
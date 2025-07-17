from agents import function_tool
from typing import Optional, List
import json
from agents import RunContextWrapper
from typing import Any

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
            
@function_tool(name_override="search_relevant_certification")
async def search_relevant_certification(search_queries: List[str]) -> Any:
    """Return a comprehensive raw list of certifications for four complementary queries.

    Args:
        search_queries: **Exactly four** English search strings used to search the internet and databases

    Returns:
        A JSON‑serialisable object containing the combined search results that
        will later be deduplicated and filtered by the calling agent.
    """

    print(f"📋 Starting certification list workflow for queries: {search_queries!r}")

    if global_orchestrator is None:
        raise RuntimeError(
            "Orchestrator not set. Call set_certification_workflow_orchestrator first."
        )

    # db = getattr(global_orchestrator, "db", None)
    return await global_orchestrator.search_relevant_certification(search_queries)

@function_tool
async def web_search(search_queries: list[str]):
    """Perform web search using the provided search queries.

    Args:
        search_queries: English search strings used to search the internet

    Returns:
        A JSON‑serialisable object containing the search results.
    """
    if global_orchestrator is None:
        raise RuntimeError(
            "Orchestrator not set. Call set_certification_workflow_orchestrator first."
        )
    return await global_orchestrator.web_search(search_queries)

@function_tool
async def compliance_research(search_queries: list[str]):
    """Perform web search and Compliance Database search to provide professional compliance answers.

    Args:
        search_queries: English search strings used to search the internet and databases

    Returns:
        A JSON‑serialisable object containing the combined search results.
    """
    if global_orchestrator is None:
        raise RuntimeError("Orchestrator not set. Call set_global_orchestrator first.")
    return await global_orchestrator.compliance_research(search_queries)


# @function_tool
# def call_rag_api(text: str, dataset_id: str = None, limit: int = 2500, similarity: int = 0, search_mode: str = "embedding", using_re_rank: bool = False):
#     from src.agent_system.internal import _call_rag_api_impl
#     return _call_rag_api_impl(text, dataset_id, limit, similarity, search_mode, using_re_rank)

# @function_tool
# def generate_search_queries(enhanced_query: str, num_queries: int = 4):
#     from . import _generate_search_queries_impl
#     return _generate_search_queries_impl(enhanced_query, num_queries)

# @function_tool
# def map_queries_to_websites(queries: list[str], domain_metadata: str):
#     from . import _map_queries_to_websites_impl
#     return _map_queries_to_websites_impl(queries, domain_metadata)

# @function_tool
# def create_parallel_queries(queries: list[str]):
#     return queries

# @function_tool
# async def run_parallel_queries(query_funcs: list[str]):
#     import asyncio
#     results = await asyncio.gather(*[func() for func in query_funcs])
#     return results

# @function_tool
# def synthesize_results(results: list[str]):
#     return "\n".join(str(r) for r in results)
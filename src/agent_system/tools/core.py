from agents import function_tool
from typing import Optional, List
import json
from agents import RunContextWrapper
from typing import Any
from agents import Agent, handoff, ItemHelpers, Runner

# Global orchestrator placeholder (set this from your app entrypoint)
global_orchestrator = None

def set_global_orchestrator(orchestrator):
    """Set the global orchestrator for tools to access"""
    global global_orchestrator
    global_orchestrator = orchestrator
    return True

#used by certification agent
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

#used by answer agent
@function_tool
async def web_search(search_query: str):
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
    return await global_orchestrator.web_search(search_query)

#used by answer agent
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

#used by flashcard agent
@function_tool
async def flashcard_web_search(search_query: str):
    """Perform web search to provide professional certification answers tailored for preparing flashcards.

    Args:
        search_query: One English search strings used to search the internet

    Returns:
        A JSON‑serialisable object containing the combined search results for the flash card information.
    """
    if global_orchestrator is None:
        raise RuntimeError("Orchestrator not set. Call set_global_orchestrator first.")
    return await global_orchestrator.certification_web_search(search_query)

# used by answer agent
@function_tool
async def prepare_flashcard(certification_name:str, context: str = None):
    """Generate a Flashcard JSON for a single certification using the FlashcardAgent.

    Args:
        certification_name: The exact name (or best-known alias) of the certification/standard to summarize.
        context: Optional short context (e.g., product type, target market/country) to help determine `mandatory`
                 and tailor the description. Pass None if unavailable.

    Returns:
        A JSON-serialisable object matching the `Flashcard` schema (name, issuing_body, region, description,
        classifications, mandatory, validity, official_link). The object is produced by running the FlashcardAgent.
    """
    if global_orchestrator is None:
        raise RuntimeError("Orchestrator not set. Call set_global_orchestrator first.")
    return await global_orchestrator.prepare_flashcard(certification_name, context)

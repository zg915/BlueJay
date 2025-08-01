from agents import function_tool
from typing import Optional, List
import json
from agents import RunContextWrapper
from typing import Any
from agents import Agent, handoff, ItemHelpers, Runner
from src.services.knowledgebase_service import kb_compliance_lookup, kb_compliance_save
from src.config.schemas import ComplianceArtifact
# Global orchestrator removed - no longer needed for clean architecture!

#used by certification agent
@function_tool
async def search_relevant_certification(search_queries: List[str]) -> Any:
    """Return a comprehensive raw list of certifications for four complementary queries.

    Args:
        search_queries: **Exactly four** English search strings used to search the internet and databases

    Returns:
        A JSON‑serialisable object containing the combined search results that
        will later be deduplicated and filtered by the calling agent.
    """

    print(f"📋 Starting certification list workflow for queries: {search_queries!r}")

    from ..orchestration import operations
    return await operations.search_relevant_certification(search_queries)

#used by answer agent
@function_tool
async def web_search(search_query: str):
    """Perform web search using the provided search queries.

    Args:
        search_queries: English search strings used to search the internet

    Returns:
        A JSON‑serialisable object containing the search results.
    """
    from ..orchestration import operations
    return await operations.web_search(search_query)

#used by answer agent
@function_tool
async def compliance_research(search_queries: list[str]):
    """Perform web search and Compliance Database search to provide professional compliance answers.

    Args:
        search_queries: English search strings used to search the internet and databases

    Returns:
        A JSON‑serialisable object containing the combined search results.
    """
    from ..orchestration import operations
    return await operations.compliance_research(search_queries)

#used by flashcard agent
@function_tool
async def flashcard_web_search(search_query: str):
    """Perform web search to provide professional certification answers tailored for preparing flashcards.

    Args:
        search_query: One English search strings used to search the internet

    Returns:
        A JSON‑serialisable object containing the combined search results for the flash card information.
    """
    from ..orchestration import operations
    return await operations.certification_web_search(search_query)

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
    from ..orchestration import operations
    return await operations.run_flashcard_agent(certification_name, context)

# used by compliance artifact ingestion agent and flashcard agent
@function_tool
async def compliance_lookup(search_query: str):
    """Perform Compliance Database search to provide relevant compliance artifacts.

    Args:
        search_query: English search strings used to search the databases

    Returns:
        A list of JSON objects containing the top hit compliance artifacts.
    """

    return await kb_compliance_lookup(search_query)

@function_tool
async def compliance_save(artifact: ComplianceArtifact, uuid: str = None):
    """Save a compliance artifact to the knowledge base.

    Args:
        object: A fully populated JSON object matching the Field-By-Field contract.
        uuid: The uuid of the weaviate object (None if creating new object).

    Returns:
        Confirmation of upsert (no additional data).
    """
    return await kb_compliance_save(artifact, uuid)


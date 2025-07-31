"""
Operations for research and search workflows
"""
import time
import asyncio
from agents import Runner


async def compliance_research(search_queries: list[str]):
    """
    Specialized workflow for compliance requests.
    Runs RAG, Web, and DB search for each query in parallel, then combines and returns all results.
    """
    print(f"📋 Starting compliance workflow for: {search_queries}")

    # Launch 3 tasks per query (RAG, Web, DB)
    tasks = []
    try:
        #TODO: change to full queries
        for query in search_queries[:1]:
            print(f"🚀 Starting Domain_web_search: {query}")
            print(f"🚀 Starting web_search: {query}")
            tasks.append(web_search(query, use_domain=True))
            tasks.append(web_search(query, use_domain=False))
            #TODO: add the RAG
            # tasks.append(_lookup_past_certifications(query))
        
        start_time = time.time()
        all_task_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        print(f"✅ All parallel tasks completed in {total_duration:.2f}s")

        print("📤 Returning all results (including errors) for agent processing...")
        return all_task_results
    except Exception as e:
        print(f"❌ Error in compliance_research: {e}")

async def search_relevant_certification(search_queries: list[str]):
    """
    Specialized workflow for certification list requests.
    Runs RAG, Web, and DB search for each query in parallel, then combines and returns all results.
    """
    print(f"📋 Starting certification list workflow for: {search_queries}")

    # Launch 3 tasks per query (RAG, Web, DB)
    tasks = []
    try:
        #TODO: change back to full queries
        for query in search_queries[:1]:
            print(f"🚀 Starting Domain_web_search: {query}")
            print(f"🚀 Starting web_search: {query}")
            tasks.append(certification_web_search(query, use_domain=True))
            tasks.append(certification_web_search(query, use_domain=False))
            #TODO: add the RAG
            # tasks.append(_lookup_past_certifications(query))
        
        start_time = time.time()  
        all_task_results = await asyncio.gather(*tasks, return_exceptions=True)
        total_duration = time.time() - start_time
        print(f"✅ All parallel tasks completed in {total_duration:.2f}s")

        print("📤 Returning all results (including errors) for agent processing...")
        return all_task_results
    except Exception as e:
        print(f"❌ Error in search_relevant_certification: {e}")

async def certification_web_search(query: str, use_domain: bool = False):
    """RAG API + Domain Search: Get domain metadata and search with domain filter"""
    from src.services.knowledgebase_service import kb_domain_search
    from src.services.perplexity_service import perplexity_certification_search
    try:
        if use_domain:
            domains = await kb_domain_search(query)
        else:
            domains = None

        result = await perplexity_certification_search(query, domains)
        return result
        
    except Exception as e:
        print(f"❌ domain web search failed: {e}")
        return {}

async def web_search(query: str, use_domain: bool = False):
    """RAG API + Domain Search: Get domain metadata and search with domain filter"""
    from src.services.knowledgebase_service import kb_domain_search
    from src.services.perplexity_service import perplexity_search
    try:
        if use_domain:
            domains = await kb_domain_search(query)
        else:
            domains = None

        result = await perplexity_search(query, domains)
        return result
        
    except Exception as e:
        print(f"❌ domain web search failed: {e}")
        return {}

async def prepare_flashcard(certification_name: str, context: str = None, orchestrator=None):
    """Generate flashcard for a certification using FlashcardAgent"""
    from ..agents import FlashcardAgent
    
    agent = FlashcardAgent(orchestrator)

    result = await Runner.run(
        agent,
        input=str({"certification_name": certification_name, "context": context}),
    )

    return str(result.final_output)
# NOTE: All @function_tool and agent-callable functions have been moved to tools/core.py.
# This file now contains only internal helpers and non-tool functions.

import os
import requests
import asyncio
import aiohttp
from src.memory.memory_service import get_recent_context as memory_get_recent_context, store_context as memory_store_context
from src.database.services import add_chat_message, create_research_request
from openai import OpenAI
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, RootModel

async def _call_rag_api_impl(text: str, dataset_id: str = None, limit: int = 2500, similarity: int = 0, search_mode: str = "embedding", using_re_rank: bool = False):
    """
    Internal implementation of RAG API call.
    """
    url = "https://fastgpt.mangrovesai.com/api/v1/chat/completions"
    api_key = os.getenv("FASTGPT_API_KEY", "fastgpt-gfpB42VPJmmJVR4QENoVR7kg3vnyKZV1OavJSNobw86ncLmUSRVoGv")
    
    if not api_key:
        print("❌ FASTGPT_API_KEY not found in environment variables")
        return []
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "stream": False,
        "details": False,
        "chatId": "test",
        "variables": {
            "query": text
        }
    }
    
    # Add appId as query parameter
    params = {
        "appId": "6862aa378829be5788710a6a"
    }
    
    try:
        print(f"🔍 Calling RAG API with query: {text[:50]}...")
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ RAG API successful")
                    print(f"    🔍 RAG response structure: {type(result)}")
                    if isinstance(result, dict):
                        print(f"    🔍 RAG response keys: {list(result.keys())}")
                    
                    # Extract domain_metadata from responseData[3].pluginOutput.domain_metadata
                    try:
                        response_data = result.get("responseData", [])
                        if len(response_data) > 3:
                            plugin_output = response_data[3].get("pluginOutput", {})
                            domain_metadata = plugin_output.get("domain_metadata", [])
                            print(f"    ✅ Extracted {len(domain_metadata)} domain metadata items from RAG API")
                            return domain_metadata
                        else:
                            print(f"    ⚠️ responseData array too short, using fallback")
                            return []
                    except Exception as e:
                        print(f"    ❌ Error extracting domain_metadata: {str(e)}")
                        return []
                else:
                    print(f"❌ RAG API failed with status {response.status}: {await response.text()}")
                    return []
            
    except Exception as e:
        print(f"❌ RAG API exception: {e}")
        return []

def generate_search_queries(enhanced_query: str, num_queries: int = 4):
    """
    Internal implementation of search query generation using LLM.
    Returns a list of 1-2 focused search queries using the Ori prompt.
    """
  
    
    # Ori prompt for intelligent query generation
    ori_prompt = """You are "Ori", Mangrove AI's compliance research agent.

INPUT
• `Research Question` – ONE English sentence or paragraph that explains exactly what information the user wants to find.

TASK
1. Read the Research Question and identify **all critical facts** (topic, object, specs, time-frame, geography, stakeholders, etc.).  
2. Craft **exactly 1-2 English search queries** that, together, cover every key fact so a web search can yield a complete answer.  
   • If a term has common synonyms or abbreviations, choose the variant most likely to surface authoritative sources.  
   • Include constraints such as date ranges or jurisdictions only if they appear in the Research Question.  
3. Return the queries in a JSON object—nothing else.

RULES
- Queries must be in English.
- Do **NOT** invent or omit user-provided details.  
- Use clear, high-signal keywords (legal names, standard numbers, agency acronyms, etc.).  
- If one query is sufficient, omit the second; if two are needed for full coverage, ensure they address different angles (e.g., technical requirement vs. regulatory context).  
- Return only the JSON object—no commentary.

Research Question: {enhanced_query}"""

    try:
        # Initialize OpenAI client with new v1.0.0 interface
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Define structured output schema
        structured_output = {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 1-2 focused search queries"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of why these queries were chosen"
                }
            },
            "required": ["queries"]
        }
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": ori_prompt.format(enhanced_query=enhanced_query)},
                {"role": "user", "content": f"Generate search queries for: {enhanced_query}"}
            ],
            max_tokens=200,
            temperature=0.1,  # Low temperature for consistent, focused queries
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        # Extract the response
        llm_response = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            parsed_response = json.loads(llm_response)
            
            # Extract queries from the structured response
            queries = parsed_response.get("queries", [])
            reasoning = parsed_response.get("reasoning", "")
            
            if not queries:
                # Fallback if no queries found
                queries = [enhanced_query + " certification requirements"]
                
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            print(f"❌ JSON parsing failed for LLM response: {llm_response}")
            queries = [enhanced_query + " certification requirements"]
            reasoning = "Fallback query generation"
        
        return {
            "queries": queries,
            "reasoning": reasoning,
            "source": "llm",
            "original_query": enhanced_query
        }
        
    except Exception as e:
        print(f"❌ LLM query generation failed: {e}")
        # Fallback to simple query generation
        return {
            "queries": [
                f"{enhanced_query} certification requirements",
                f"{enhanced_query} regulatory standards"
            ],
            "reasoning": "Fallback query generation due to LLM error",
            "source": "fallback",
            "original_query": enhanced_query
        }

def map_queries_to_websites(queries: list[str], domain_metadata: str):
    """
    Map generated queries to relevant websites from domain metadata.
    Returns mapping of queries to websites.
    """
    # This would use LLM to intelligently map queries to websites
    # For now, return a structured mapping
    # Parse domain_metadata as JSON string
    import json
    try:
        metadata = json.loads(domain_metadata) if isinstance(domain_metadata, str) else domain_metadata
    except:
        metadata = {"websites": []}
    
    websites = metadata.get("websites", [])
    mapping = {}
    
    for query in queries:
        # Simple mapping logic - in practice, this would use LLM
        relevant_sites = [site for site in websites if any(keyword in query.lower() for keyword in ["certification", "regulatory", "compliance"])]
        mapping[query] = relevant_sites
    
    return mapping

class Certification(BaseModel):
    certificate_name: str
    certificate_description: str
    legal_regulation: str
    legal_text_excerpt: str
    legal_text_meaning: str
    registration_fee: str
    is_required: bool

class CertificationList(RootModel[list[Certification]]):
    pass

async def _perplexity_domain_search_impl(query: str, domains: list = None):
    """
    Internal implementation of Perplexity domain search using structured output.
    """
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not found in environment variables")
        return []

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    from src.config.prompts import PERPLEXITY_LIST_GENERAL_PROMPT, PERPLEXITY_LIST_DOMAIN_PROMPT
    if domains and len(domains) > 0:
        system_prompt = PERPLEXITY_LIST_DOMAIN_PROMPT
        domain_list = ", ".join(domains)
        enhanced_query = f"{query} (search across these domains: {domain_list})"
    else:
        system_prompt = PERPLEXITY_LIST_GENERAL_PROMPT
        enhanced_query = query

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Search for: {enhanced_query}"}
    ]

    payload = {
        "model": "sonar-pro",
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": CertificationList.model_json_schema()}
        }
    }
    if domains and len(domains) == 1:
        payload["domain_search"] = domains[0]

    try:
        if domains and len(domains) > 1:
            print(f"🔍 Calling Perplexity API with {len(domains)} domains: {domains[:3]}..., query: {query[:50]}...")
        else:
            domain_str = domains[0] if domains else "general"
            print(f"🔍 Calling Perplexity API with domain: {domain_str}, query: {query[:50]}...")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Perplexity API successful")
                    # Expecting result["choices"][0]["message"]["content"] to be a JSON array
                    content = result["choices"][0]["message"]["content"]
                    print(f"    🔍 Perplexity content preview: {content[:200]}...")
                    try:
                        cert_list = CertificationList.model_validate_json(content)
                        print(f"✅ Parsed {len(cert_list.root)} certifications from Perplexity response")
                        # Return as list of dicts for downstream compatibility
                        return [c.model_dump() for c in cert_list.root]
                    except Exception as e:
                        print(f"❌ Pydantic parsing failed: {e}")
                        return []
                else:
                    print(f"❌ Perplexity API failed with status {response.status}: {await response.text()}")
                    return []
    except Exception as e:
        print(f"❌ Perplexity API exception: {e}")
        return []

def perplexity_domain_search(query: str, domains: list = None):
    """
    Perform web search using Perplexity API with domain-specific search.
    Now accepts a list of domains to search across all at once.
    """
    return _perplexity_domain_search_impl(query, domains)

def create_parallel_queries(queries: list[str]):
    """
    Create a list of parallel queries to execute.
    """
    return queries

async def run_parallel_queries(query_funcs: list[str]):
    """
    Run multiple query functions in parallel.
    """
    results = await asyncio.gather(*[func() for func in query_funcs])
    return results

def synthesize_results(results: list[str]):
    """
    Synthesize multiple results into a single coherent response.
    """
    return "\n".join(str(r) for r in results)

# Internal async functions for DB operations (not decorated)
async def store_message_db(session_id: str, content: str, db, role: str = "user", reply_to: str = None):
    return await add_chat_message(db, session_id, content, role=role, reply_to=reply_to)

async def get_recent_context_db(db, session_id: str, chat_length: int):
    return await memory_get_recent_context(db, session_id, chat_length)

async def store_final_response_db(user_id: str, session_id: str, response: str, db):
    # Final response storage removed - this function is now a no-op
    return True

async def store_research_request_db(session_id: str, question: str, result: str, db, workflow_type: str, message_id: str = None):
    return await create_research_request(db, session_id, question, workflow_type, message_id=message_id)

async def store_context_db(db, session_id: str):
    return await memory_store_context(db, session_id) 
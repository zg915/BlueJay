# NOTE: All @function_tool and agent-callable functions have been moved to tools/core.py.
# This file now contains only internal helpers and non-tool functions.

import os
import requests
import asyncio
import aiohttp
from src.memory.memory_service import get_recent_context as memory_get_recent_context, store_context as memory_store_context
from src.database.services import add_chat_message, create_research_request
from src.knowledgebase.knowledgebase_service import domain_search_kb
from src.config.prompts import PERPLEXITY_CERTIFICATION_PROMPT, PERPLEXITY_GENERAL_PROMPT
from openai import OpenAI
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, RootModel
from src.config.output_structure import Certifications_Structure

async def _perplexity_certification_search(query: str, domains: list = None):
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

    messages = [
        {"role": "system", "content": PERPLEXITY_CERTIFICATION_PROMPT},
        {"role": "user", "content": query}
    ]

    payload = {
        "model": "sonar-pro",
        "messages": messages,
        # "max_tokens": 1000,
        "temperature": 0.1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"schema": Certifications_Structure.schema()}
        }
    }
    if domains:
        payload["search_domain_filter"] = domains

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Perplexity API successful")
                    # Expecting result["choices"][0]["message"]["content"] to be a JSON array
                    content = result["choices"][0]["message"]["content"]
                    # Parse the JSON content returned by Perplexity API
                    try:
                        content_json = json.loads(content)
                    except json.JSONDecodeError as e:
                        print(f"❌ Failed to parse JSON content: {e}")
                        content_json = content["certifications"]
                    citations = result.get('citations', [])
                    return {"certifications": content_json, "citations": citations}
                else:
                    print(f"❌ Perplexity API failed with status {response.status}: {await response.text()}")
                    return []
    except Exception as e:
        print(f"❌ Perplexity API exception: {e}")
        return []


async def _perplexity_search(query: str, domains: list = None):
    """
    Internal implementation of Perplexity domain search.
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

    messages = [
        {"role": "system", "content": PERPLEXITY_GENERAL_PROMPT},
        {"role": "user", "content": query}
    ]

    payload = {
        "model": "sonar-pro",
        "messages": messages,
        # "max_tokens": 1000,
        "temperature": 0.1
    }
    if domains:
        payload["search_domain_filter"] = domains

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Perplexity API successful")
                    # Expecting result["choices"][0]["message"]["content"] to be a JSON array
                    content = result["choices"][0]["message"]["content"]
                    citations = result.get('citations', [])
                    # Parse the JSON content returned by Perplexity API
                    return {"content": content, "citations": citations}
                else:
                    print(f"❌ Perplexity API failed with status {response.status}: {await response.text()}")
                    return []
    except Exception as e:
        print(f"❌ Perplexity API exception: {e}")
        return []

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

async def _domain_search_kb(query: str):
    return await domain_search_kb(query)


"""
Perplexity API service functions
"""
import os
import aiohttp
from src.config.prompts import PERPLEXITY_PROMPT


async def perplexity_search(query: str, domains: list = None):
    """
    Perplexity domain search for general queries.
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
        {"role": "system", "content": PERPLEXITY_PROMPT},
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
                    print(f"🛜 Perplexity API successful")
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
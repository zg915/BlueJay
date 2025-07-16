# memory_service.py
"""
Handles fetching and storing recent context for user sessions.
"""

import os
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.services import (
    get_last_n_messages,
    get_latest_summary,
    upsert_summary
)

# Fetch last 10 messages and latest summary for a session
async def get_recent_context(db: AsyncSession, session_id: str, history_length: int = 9):
    """
    Fetches the latest summary and last 10 messages after the summary for the session.
    Returns formatted context suitable for AI agents.
    """
    # Get latest summary
    summary_obj = await get_latest_summary(db, session_id)
    summary = summary_obj.summary if summary_obj else None
    
    # Get last 10 messages after the summary
    messages = await get_last_n_messages(db, session_id, history_length)
    
    # Format messages for better readability
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "role": msg.role,
            "content": msg.content,
        })

    return {
        "summary": summary, 
        "messages": formatted_messages,
        "message_count": len(formatted_messages),
    }

# Store summary after every 10th message
async def store_context(db: AsyncSession, session_id: str):
    """
    After every 10th message, generate a summary using LLM and upsert into conversation_memory.
    """
    # Fetch all messages for the session
    all_messages = await get_last_n_messages(db, session_id, 10000)  # Get all
    message_count = len(all_messages)
    if message_count % 10 == 0:
        # Concatenate all messages
        conversation_text = "\n".join([msg.content for msg in all_messages])
        # Generate summary using OpenAI LLM with new API format

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        prompt = f"Summarize the following conversation:\n{conversation_text}"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}],
            max_tokens=256
        )
        summary = response.choices[0].message.content
        # Upsert summary in DB
        await upsert_summary(
            db,
            session_id,
            summary,
            up_to_message_order=message_count,
            strategy="llm"
        ) 
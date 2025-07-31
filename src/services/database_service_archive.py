"""
Database service functions - ARCHIVED (unused functions)
These functions were moved here from database_service.py as they are not currently being used.
"""
import os
import logging
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update
from sqlalchemy.exc import NoResultFound, IntegrityError
from fastapi.encoders import jsonable_encoder
from openai import OpenAI
from .models import ChatSession, ChatMessage, ResearchRequest, ConversationMemory

logger = logging.getLogger(__name__)

# ARCHIVED - Never imported or used anywhere
async def create_chat_session(session: AsyncSession, user_id: str):
    new_session = ChatSession(user_id=user_id)
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    return new_session

async def get_chat_session(session: AsyncSession, session_id: str):
    result = await session.execute(select(ChatSession).where(ChatSession.session_id == session_id))
    chat_session = result.scalar_one_or_none()
    if not chat_session:
        raise NoResultFound(f"ChatSession {session_id} not found.")
    return chat_session

# ARCHIVED - Only used by unused wrapper functions
async def create_research_request(session: AsyncSession, session_id: str, question: str, workflow_type: str, message_id: str = None):
    req = ResearchRequest(session_id=session_id, enhanced_query=question, workflow_type=workflow_type, message_id=message_id)
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req

async def get_latest_summary(session: AsyncSession, session_id: str):
    result = await session.execute(
        select(ConversationMemory)
        .where(ConversationMemory.session_id == session_id)
        .order_by(ConversationMemory.up_to_message_order.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

async def upsert_summary(session: AsyncSession, session_id: str, summary: str, up_to_message_order: int, strategy: str = "llm"):
    # Try to find existing summary for this up_to_message_order
    result = await session.execute(
        select(ConversationMemory)
        .where(ConversationMemory.session_id == session_id)
        .where(ConversationMemory.up_to_message_order == up_to_message_order)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.summary = summary
        existing.summarization_strategy = strategy
        await session.commit()
        await session.refresh(existing)
        return existing
    else:
        new_summary = ConversationMemory(
            session_id=session_id,
            summary=summary,
            up_to_message_order=up_to_message_order,
            summarization_strategy=strategy
        )
        session.add(new_summary)
        await session.commit()
        await session.refresh(new_summary)
        return new_summary

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

async def get_last_n_messages(session: AsyncSession, session_id: str, n: int = 9):
    # 1) Fetch up to n recent messages
    recent_rs = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.message_order.desc())
        .limit(n)
    )
    messages = recent_rs.scalars().all()

    # 2) If underflow and this is a follow-up, pull from the source session
    if len(messages) < n:
        info_rs = await session.execute(
            select(ChatSession.session_type, ChatSession.source_message_metadata)
            .where(ChatSession.session_id == session_id)
            .limit(1)
        )
        sess_info = info_rs.one_or_none()
        if sess_info:
            sess_type, metadata = sess_info
            if sess_type == "follow_up" and metadata:
                src_msg_id = metadata["source_message_id"]
                src_rs = await session.execute(
                    select(ChatMessage.session_id, ChatMessage.message_order)
                    .where(ChatMessage.message_id == src_msg_id)
                    .limit(1)
                )
                src_info = src_rs.one_or_none()
                if src_info:
                    src_session_id, src_order = src_info
                    fallback_rs = await session.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == src_session_id)
                        .where(ChatMessage.message_order <= src_order)
                        .where(ChatMessage.is_summarized == False)
                        .order_by(ChatMessage.message_order.desc())
                        .limit(n - len(messages))
                    )
                    messages += fallback_rs.scalars().all()

    # 3) Return in chronological order
    return list(reversed(messages))

# ARCHIVED - Unused wrapper functions (imported but never called)
async def store_final_response_db(user_id: str, session_id: str, response: str, db):
    # Final response storage removed - this function is now a no-op
    return True

async def store_research_request_db(session_id: str, question: str, result: str, db, workflow_type: str, message_id: str = None):
    return await create_research_request(db, session_id, question, workflow_type, message_id=message_id)

async def store_context_db(db, session_id: str):
    return await store_context(db, session_id)
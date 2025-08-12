"""
Database service functions - Simplified (only actively used functions)
"""
import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update
from fastapi.encoders import jsonable_encoder
from .models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)

async def db_store_message(
    db: AsyncSession,
    session_id: str,
    content: str,
    certifications: list | None = None,
    role: str = "user",
    reply_to: str | None = None,
    type: str = "text",
    is_cancelled: bool = False
):
    """
    Store a message in the database
    """
    try:
        # 1) Determine next message_order
        next_rs = await db.execute(
            select(func.coalesce(func.max(ChatMessage.message_order), 0) + 1)
            .where(ChatMessage.session_id == session_id)
        )
        message_order = next_rs.scalar_one()

        # 2) Construct a unique message_id
        timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        message_id = f"msg_{timestamp_str}_{session_id}"

        # 3) Create and persist the ChatMessage
        msg = ChatMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            certifications=certifications,
            message_order=message_order,
            reply_to=reply_to,
            type=type,
            is_cancelled=is_cancelled
        )
        db.add(msg)

        # 4) Update the parent ChatSession counters
        await db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(
                message_count=ChatSession.message_count + 1,
                updated_at=datetime.datetime.utcnow(),
            )
        )

        # 5) Commit and refresh
        await db.commit()
        await db.refresh(msg)
        return jsonable_encoder(msg)
    except Exception as e:
        logger.error(f"Error storing message: {e}")
        await db.rollback()
        raise

async def db_get_recent_context(db: AsyncSession, session_id: str, chat_length: int):
    import json
    formatted_messages = []
    
    # 1) Get most up to date summary
    latest_memory = await db_get_latest_memory(db, session_id)
    if latest_memory:
        formatted_messages.append({
            "role": "assistant",
            "content": f"<conversation_summary version=\"1\" asof=\"{latest_memory.timestamp}Z\" source=\"db\" schema=\"mangrove:conversation_summary:v1\">{{\"summary\": {json.dumps(latest_memory.summary)}}}</conversation_summary>"
        })

    # 2) Fetch up to n recent messages
    recent_rs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.message_order.desc())
        .limit(chat_length)
    )
    messages = recent_rs.scalars().all()

    # 3) If underflow and this is a follow-up, pull from the source session
    if len(messages) < chat_length:
        info_rs = await db.execute(
            select(ChatSession.session_type, ChatSession.source_message_metadata)
            .where(ChatSession.session_id == session_id)
            .limit(1)
        )
        sess_type, metadata = info_rs.one()
        if sess_type == "follow_up":
            src_msg_id = metadata["source_message_id"]
            src_rs = await db.execute(
                select(ChatMessage.session_id, ChatMessage.message_order)
                .where(ChatMessage.message_id == src_msg_id)
                .limit(1)
            )
            src_session_id, src_order = src_rs.one()

            fallback_rs = await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == src_session_id)
                .where(ChatMessage.message_order <= src_order)
                .where(ChatMessage.is_summarized == False)
                .order_by(ChatMessage.message_order.desc())
                .limit(chat_length - len(messages))
            )
            messages += fallback_rs.scalars().all()

    # 4) Return in chronological order
    for msg in list(reversed(messages)):
        if msg.role == "assistant" and msg.certifications:
            formatted_messages.append({
                "role": "assistant",
                "content": f"<flashcard_context version=\"1\" asof=\"{msg.timestamp}Z\" source=\"db\" count=\"{len(msg.certifications)}\" schema=\"mangrove:flashcard_context:v1\">{{\"flashcards\": {msg.certifications}}}</flashcard_context>"
            })
            
        formatted_messages.append({
            "role": msg.role,
            "content": msg.content,
        })

    # Get the latest message order
    latest_message_order = messages[0].message_order if messages else 0
    
    return {
        "messages": formatted_messages,
        "message_count": len(formatted_messages),
        "latest_message_order": latest_message_order,
    }

async def db_update_memory(db: AsyncSession, session_id: str, summary: str, message_order: int, strategy: str = "auto_every_6_messages"):
    """
    Store conversation summary in ConversationMemory table
    """
    from .models import ConversationMemory
    
    try:
        memory = ConversationMemory(
            session_id=session_id,
            summary=summary,
            up_to_message_order=message_order,
            summarization_strategy=strategy
        )
        
        db.add(memory)
        await db.commit()
        await db.refresh(memory)
        
        return memory
    except Exception as e:
        logger.error(f"Error storing conversation memory: {e}")
        await db.rollback()
        raise

async def db_get_latest_memory(db: AsyncSession, session_id: str):
    """
    Get the latest conversation memory for a session (by highest message_order)
    """
    from .models import ConversationMemory
    
    result = await db.execute(
        select(ConversationMemory)
        .where(ConversationMemory.session_id == session_id)
        .order_by(ConversationMemory.up_to_message_order.desc())
        .limit(1)
    )
    
    return result.scalar_one_or_none()
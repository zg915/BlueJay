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

async def db_get_recent_context(db: AsyncSession, session_id: str, chat_length: int):
    # 1) Fetch up to n recent messages
    recent_rs = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.message_order.desc())
        .limit(chat_length)
    )
    messages = recent_rs.scalars().all()

    # 2) If underflow and this is a follow-up, pull from the source session
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

    # 3) Return in chronological order

    formatted_messages = []
    for msg in list(reversed(messages)):
        formatted_messages.append({
            "role": msg.role,
            "content": msg.content,
        })

    return {
        "summary": None, 
        "messages": formatted_messages,
        "message_count": len(formatted_messages),
    }

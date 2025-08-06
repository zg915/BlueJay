"""
Database service functions - Simplified (only actively used functions)
"""
import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, update
from fastapi.encoders import jsonable_encoder
from .models import ChatSession, ChatMessage, AgentTrace, AgentSpan

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

async def db_store_trace(
    db: AsyncSession,
    trace_id: str,
    workflow_name: str,
    started_at: datetime.datetime,
    ended_at: datetime.datetime,
    status: str = None,
    trace_metadata: dict = None,
    usage_json: dict = None,
    raw_json: dict = None,
    message_id: str = None
):
    """
    Store an agent trace in the database
    """
    try:
        # Check if trace already exists (avoid duplicates)
        existing = await db.execute(
            select(AgentTrace).where(AgentTrace.trace_id == trace_id)
        )
        if existing.scalar_one_or_none():
            return None
        
        # Create and persist the AgentTrace
        trace = AgentTrace(
            trace_id=trace_id,
            workflow_name=workflow_name,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            trace_metadata=trace_metadata or {},
            usage_json=usage_json or {},
            raw_json=raw_json or {},
            message_id=message_id
        )
        db.add(trace)
        await db.commit()
        await db.refresh(trace)
        return jsonable_encoder(trace)
        
    except Exception as e:
        logger.error(f"Failed to store trace {trace_id}: {e}")
        await db.rollback()
        return None

async def db_store_spans(
    db: AsyncSession,
    spans_data: list
):
    """
    Store multiple agent spans in the database
    """
    try:
        span_records = []
        for span_data in spans_data:
            span_record = AgentSpan(
                span_id=span_data["span_id"],
                trace_id=span_data["trace_id"],
                parent_id=span_data.get("parent_id"),
                name=span_data["name"],
                span_type=span_data["span_type"],
                started_at=span_data["started_at"],
                ended_at=span_data["ended_at"],
                data=span_data["data"]
            )
            span_records.append(span_record)
        
        db.add_all(span_records)
        await db.commit()
        return len(span_records)
        
    except Exception as e:
        logger.error(f"Failed to store spans: {e}")
        await db.rollback()
        return 0

def parse_trace_timestamp(timestamp_str: str = None) -> datetime.datetime:
    """
    Parse timestamp string to datetime object for trace storage
    """
    if not timestamp_str:
        return datetime.datetime.utcnow()
    try:
        # Handle ISO format timestamps from OpenAI SDK
        return datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return datetime.datetime.utcnow()

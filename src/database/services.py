# services.py
"""
Async database access functions for chat messages, sessions, research requests, and final responses.
"""
import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import func, update
import datetime
from sqlalchemy.exc import NoResultFound, IntegrityError
from .models import ChatSession, ChatMessage, ResearchRequest, ConversationMemory
import datetime
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)

class DatabaseService:
    """Database service for managing async connections"""
    
    def __init__(self):
        self.engine = None
        self.async_session = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize database connection"""
        try:
            # Get database configuration from environment
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME", "tic_research")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")
            
            # Build connection string
            connection_string = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            
            # Create async engine
            self.engine = create_async_engine(
                connection_string,
                echo=False,  # Set to True for SQL debugging
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            # Create session factory
            self.async_session = sessionmaker(
                self.engine, 
                class_=AsyncSession, 
                expire_on_commit=False
            )
            
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    async def get_session(self):
        """Get an async database session"""
        async with self.async_session() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Database session error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()

# Create global database service instance
db_service = DatabaseService()

# --- Chat Sessions ---
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

# --- Chat Messages ---
async def add_chat_message(
    session: AsyncSession,
    session_id: str,
    content: str,
    role: str = "user",
    reply_to: str | None = None,
    type: str = "text",
):
    """
    Add a chat message, mirroring the logic used in the newer DatabaseService.store_message
    but keeping the ORM‑centric style already used in this module.
    """
    # 1) Determine next message_order if not provided
    next_rs = await session.execute(
        select(func.coalesce(func.max(ChatMessage.message_order), 0) + 1)
        .where(ChatMessage.session_id == session_id)
    )
    message_order = next_rs.scalar_one()

    # 2) Construct a unique message_id
    timestamp_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    message_id = f"msg_{timestamp_str}_{session_id}"

    # 3) Create and persist the ChatMessage ORM object
    msg = ChatMessage(
        message_id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        message_order=message_order,
        reply_to=reply_to,
        type=type,
    )
    session.add(msg)

    # 4) Update the parent ChatSession counters
    await session.execute(
        update(ChatSession)
        .where(ChatSession.session_id == session_id)
        .values(
            message_count=ChatSession.message_count + 1,
            updated_at=datetime.datetime.utcnow(),
        )
    )

    # 5) Commit and refresh
    await session.commit()
    await session.refresh(msg)
    return jsonable_encoder(msg)

async def get_last_n_messages(session: AsyncSession, session_id: str, n: int = 9):
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.timestamp.desc())
        .limit(n)
    )
    return result.scalars().all()

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
        sess_type, metadata = info_rs.one()
        if sess_type == "follow_up":
            src_msg_id = metadata["source_message_id"]
            src_rs = await session.execute(
                select(ChatMessage.session_id, ChatMessage.message_order)
                .where(ChatMessage.message_id == src_msg_id)
                .limit(1)
            )
            src_session_id, src_order = src_rs.one()

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

# --- Research Requests ---
async def create_research_request(session: AsyncSession, session_id: str, question: str, workflow_type: str, message_id: str = None):
    req = ResearchRequest(session_id=session_id, enhanced_query=question, workflow_type=workflow_type, message_id=message_id)
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req

async def get_research_request(session: AsyncSession, request_id: str):
    result = await session.execute(select(ResearchRequest).where(ResearchRequest.request_id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise NoResultFound(f"ResearchRequest {request_id} not found.")
    return req

# --- Conversation Memory (Summaries) ---
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

async def get_last_n_messages_after_summary(session: AsyncSession, session_id: str, after_order: int, n: int = 10):
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .where(ChatMessage.message_order > after_order)
        .order_by(ChatMessage.timestamp.asc())
        .limit(n)
    )
    return result.scalars().all() 
# models.py
"""
SQLAlchemy models for chat messages, sessions, research requests, and final responses.
"""
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
import datetime
from sqlalchemy.sql import func

Base = declarative_base()

class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    session_id = Column(String, primary_key=True, server_default=func.uuid_generate_v4())
    user_id = Column(String, nullable=False)
    session_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    current_memory_id = Column(String, nullable=True)
    message_count = Column(Integer, default=0)
    starred = Column(Boolean, default=False)
    session_type = Column(String, default='main')
    source_message_metadata = Column(JSON, nullable=True)
    messages = relationship('ChatMessage', back_populates='session')

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    message_id = Column(String, primary_key=True, server_default=func.uuid_generate_v4())
    session_id = Column(String, ForeignKey('chat_sessions.session_id'), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    message_order = Column(Integer, nullable=True)
    is_summarized = Column(Boolean, default=False)
    reply_to = Column(String, nullable=True)
    type = Column(String, nullable=True)
    is_cancelled = Column(Boolean, default=False)
    cancellation_timestamp = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    certifications = Column(JSON, default=list)
    session = relationship('ChatSession', back_populates='messages')

class ResearchRequest(Base):
    __tablename__ = 'research_requests'
    request_id = Column(String, primary_key=True, server_default=func.uuid_generate_v4())
    session_id = Column(String, ForeignKey('chat_sessions.session_id'), nullable=False)
    message_id = Column(String, nullable=True)
    enhanced_query = Column(Text, nullable=False)
    workflow_type = Column(String, nullable=False)
    domain_metadata_used = Column(JSON, server_default='{}')
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    processing_time = Column(Integer, nullable=True)
    status = Column(String, default='pending')

class ConversationMemory(Base):
    __tablename__ = 'conversation_memory'
    memory_id = Column(String, primary_key=True, server_default=func.uuid_generate_v4())
    session_id = Column(String, nullable=False)
    summary = Column(Text)
    up_to_message_order = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    summarization_strategy = Column(String) 
"""
FastAPI endpoints for OpenAI Agents SDK
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import asyncio
from src.agent_system.orchestration import WorkflowOrchestrator
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

# Pydantic models for request/response
class ChatRequest(BaseModel):
    session_id: str
    content: str

class ChatResponse(BaseModel):
    response: str
    question_type: Optional[str] = None
    enhanced_query: Optional[str] = None

class SessionRequest(BaseModel):
    user_id: str

class SessionResponse(BaseModel):
    session_id: str
    user_id: str

class HealthResponse(BaseModel):
    status: str
    message: str

# Initialize orchestrator
print("🔧 Initializing WorkflowOrchestrator for endpoints...")
orchestrator = WorkflowOrchestrator()
print("✅ WorkflowOrchestrator initialized for endpoints")

# Streaming chat endpoint
async def chat_stream(request: ChatRequest, db: AsyncSession):
    print(f"\n📡 Streaming chat request received")
    print(f"💬 Session: {request.session_id}")
    print(f"📝 Content: {request.content}")
    def to_serializable(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        elif isinstance(obj, list):
            return [to_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: to_serializable(v) for k, v in obj.items()}
        return obj

    async def event_stream():
        async for result in orchestrator.handle_user_question(
            request.session_id,
            request.content,
            db
        ):
            yield f"data: {json.dumps({'status': 'stream', 'response': to_serializable(result)}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'status': 'end'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

# Non-streaming chat endpoint
async def chat_simple(request: ChatRequest, db: AsyncSession):
    """
    Non-streaming chat endpoint that returns a single response
    """
    print(f"\n💬 Simple chat request received")
    print(f"💬 Session: {request.session_id}")
    print(f"📝 Content: {request.content}")
    
    try:
        result = await orchestrator.handle_user_question(
            request.session_id, 
            request.content,
            db
        )
        
        print(f"✅ Workflow completed, returning result")
        
        # Convert result to JSON string if it's a list
        if isinstance(result, list):
            response_text = json.dumps(result, ensure_ascii=False)
            print(f"📝 Converting {len(result)} JSON objects to string for API response")
        else:
            response_text = str(result)
        
        return ChatResponse(
            response=response_text,
            question_type="unknown",  # Could be extracted from triage response
            enhanced_query=request.content  # Could be extracted from triage response
        )
    
    except Exception as e:
        print(f"❌ Error in simple chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
async def health_check():
    """
    Health check endpoint
    """
    print("🏥 Health check requested")
    return HealthResponse(
        status="healthy",
        message="Agentic workflow system is running"
    )

# Session management endpoints
async def create_session(request: SessionRequest, db: AsyncSession):
    """
    Create a new chat session
    """
    print(f"\n➕ Creating new session")
    print(f"👤 User: {request.user_id}")
    
    try:
        from src.database.services import create_chat_session
        
        # Create session in database
        chat_session = await create_chat_session(db, request.user_id)
        print(f"✅ Session created with ID: {chat_session.session_id}")
        
        return SessionResponse(
            session_id=chat_session.session_id,
            user_id=request.user_id
        )
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")

async def get_session_history(session_id: str, db: AsyncSession):
    """
    Get chat history for a session
    """
    print(f"\n📚 Getting session history")
    print(f"💬 Session: {session_id}")
    
    try:
        from src.database.services import get_chat_session, get_last_n_messages
        
        # Get the session
        session = await get_chat_session(db, session_id)
        print(f"✅ Session found")
        
        # Get the last 50 messages for this session
        messages = await get_last_n_messages(db, session_id, 50)
        print(f"📝 Found {len(messages)} messages")
        
        # Format messages for response
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({
                "id": msg.message_id,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "role": msg.role,
                "message_order": msg.message_order
            })
        
        return {
            "session_id": session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "messages": formatted_messages
        }
    except Exception as e:
        print(f"❌ Error getting session history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}") 
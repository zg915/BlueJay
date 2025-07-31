"""
FastAPI endpoints for OpenAI Agents SDK
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.agent_system.orchestration import WorkflowOrchestrator
from src.agent_system.session_manager import workflow_sessions


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
    context = workflow_sessions.create(request.session_id)

    async def event_stream():
      
        try:
            async for result in orchestrator.handle_user_question(
                request.session_id,
                request.content,
                db,
                context=context
            ):
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            print(f"🛑 Workflow cancelled for session: {request.session_id}")
        finally:
            workflow_sessions.remove(request.session_id)
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
            # response_text = json.dumps(result, ensure_ascii=False)
            response_text = json.dumps(result)
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

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
    user_id: str
    session_id: str
    message: str

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
    """
    Streaming chat endpoint that provides real-time updates
    """
    print(f"\n📡 Streaming chat request received")
    print(f"👤 User: {request.user_id}")
    print(f"💬 Session: {request.session_id}")
    print(f"📝 Message: {request.message}")
    
    try:
        # Stream the workflow with real-time updates
        async def generate():
            # Send initial status
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Starting workflow...'})}\n\n"
            
            # Start the workflow and get raw results
            raw_results = await orchestrator.handle_certification_list_workflow(
                request.message, 
                {'messages': []}, 
                db
            )
            
            yield f"data: {json.dumps({'status': 'searching', 'message': f'Found {len(raw_results)} raw results, processing with OpenAI...'})}\n\n"
            
            # Stream OpenAI response
            from src.services.openai_service import openai_service
            
            # Format raw results for OpenAI
            results_text = orchestrator._format_raw_results_for_openai(raw_results)
            prompt = f"""
You are an expert assistant. Given the following raw certification results, deduplicate and synthesize them into a list of JSON objects. 
Each object must have the following fields:
- certificate_name
- certificate_description
- legal_regulation
- legal_text_excerpt
- legal_text_meaning
- registration_fee
- is_required

Return ONLY a JSON array of objects, no markdown, no explanation, no extra text.

Original Query: {request.message}

Raw Results ({len(raw_results)} items):
{results_text}
"""
            
            # Stream OpenAI response
            stream = openai_service.client.chat.completions.create(
                model=openai_service.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that processes and synthesizes search results. Provide clear, well-organized responses."},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Collect the streaming response
            full_response = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    # Stream each chunk
                    yield f"data: {json.dumps({'status': 'streaming', 'chunk': content})}\n\n"
            
            # Parse the final JSON response
            parsed_json = orchestrator._clean_and_parse_json_response(full_response)
            
            # Send final result
            yield f"data: {json.dumps({'status': 'complete', 'response': parsed_json})}\n\n"
            
            # Send end marker
            yield f"data: {json.dumps({'status': 'end'})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
    
    except Exception as e:
        print(f"❌ Error in streaming chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Non-streaming chat endpoint
async def chat_simple(request: ChatRequest, db: AsyncSession):
    """
    Non-streaming chat endpoint that returns a single response
    """
    print(f"\n💬 Simple chat request received")
    print(f"👤 User: {request.user_id}")
    print(f"💬 Session: {request.session_id}")
    print(f"📝 Message: {request.message}")
    
    try:
        result = await orchestrator.handle_user_question(
            request.user_id, 
            request.session_id, 
            request.message,
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
            enhanced_query=request.message  # Could be extracted from triage response
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
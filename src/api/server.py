"""
FastAPI server configuration for OpenAI Agents SDK
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_session
from src.database.services import db_service
from .endpoints import (
    chat_stream, chat_simple, health_check, 
    create_session, get_session_history,
    ChatRequest, SessionRequest
)
from src.agent_system.session_manager import workflow_sessions
from pydantic import BaseModel

class StopRequest(BaseModel):
    session_id: str

# Create FastAPI app
app = FastAPI(
    title="Agentic Workflow API",
    description="A modular, agent-driven workflow for compliance/certification research",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
async def get_db():
    """Get database session with error handling"""
    try:
        async for session in db_service.get_session():
            yield session
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# Register routes
@app.post("/ask/stream")
async def streaming_chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Streaming chat endpoint with real-time updates"""
    return await chat_stream(request, db)

@app.post("/stop")
async def stop_workflow(request: StopRequest):
    workflow_sessions.stop(request.session_id)
    return {"status": "cancelled", "session_id": request.session_id}

@app.post("/ask")
async def simple_chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Non-streaming chat endpoint"""
    return await chat_simple(request, db)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return await health_check()

@app.post("/sessions")
async def create_new_session(request: SessionRequest, db: AsyncSession = Depends(get_db)):
    """Create a new chat session"""
    return await create_session(request, db)

@app.get("/sessions/{session_id}/history")
async def get_history(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get chat history for a session"""
    return await get_session_history(session_id, db)

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Agentic Workflow API",
        "version": "1.0.0",
        "endpoints": {
            "streaming_chat": "/ask/stream",
            "simple_chat": "/ask",
            "health": "/health",
            "create_session": "/sessions",
            "session_history": "/sessions/{session_id}/history"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
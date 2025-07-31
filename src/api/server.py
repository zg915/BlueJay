"""
FastAPI server configuration for OpenAI Agents SDK
"""
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from src.services import get_async_session
from .endpoints import (
    chat_stream, chat_simple, health_check, 
    ChatRequest, SessionRequest
)
from src.agent_system.session_manager import workflow_sessions
from pydantic import BaseModel

class StopRequest(BaseModel):
    session_id: str

class TestAgentRequest(BaseModel):
    query: str = "CE marking requirements for electronics"

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
        async for session in get_async_session():
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

@app.post("/test/background-agent")
async def test_background_agent(request: TestAgentRequest):
    """Test endpoint for background compliance ingestion agent"""
    from src.agent_system.orchestration.operations import test_background_compliance_agent
    return await test_background_compliance_agent(request.query)

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
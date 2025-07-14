import pytest
import httpx
import os

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_create_session():
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/sessions", json={"user_id": "testuser"})
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        return data["session_id"]

@pytest.mark.asyncio
async def test_simple_chat():
    async with httpx.AsyncClient() as client:
        # Create session first
        resp = await client.post(f"{BASE_URL}/sessions", json={"user_id": "testuser"})
        session_id = resp.json()["session_id"]
        # Send chat
        chat_resp = await client.post(f"{BASE_URL}/ask", json={
            "user_id": "testuser",
            "session_id": session_id,
            "message": "What is RoHS?"
        })
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        assert "response" in data
        assert data["response"]

@pytest.mark.asyncio
async def test_streaming_chat():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create session first
        resp = await client.post(f"{BASE_URL}/sessions", json={"user_id": "testuser"})
        session_id = resp.json()["session_id"]
        # Send streaming chat
        stream_resp = await client.post(f"{BASE_URL}/ask/stream", json={
            "user_id": "testuser",
            "session_id": session_id,
            "message": "List 5 ISO standards for electronics."
        })
        assert stream_resp.status_code == 200
        # Check for streaming markers in response text
        text = stream_resp.text
        assert "status" in text
        assert "response" in text or "processing" in text

@pytest.mark.asyncio
async def test_session_history():
    async with httpx.AsyncClient() as client:
        # Create session first
        resp = await client.post(f"{BASE_URL}/sessions", json={"user_id": "testuser"})
        session_id = resp.json()["session_id"]
        # Get history
        hist_resp = await client.get(f"{BASE_URL}/sessions/{session_id}/history")
        assert hist_resp.status_code == 200
        data = hist_resp.json()
        assert data["session_id"] == session_id
        assert "messages" in data 
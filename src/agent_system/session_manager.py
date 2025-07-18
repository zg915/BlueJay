import asyncio
import uuid
from datetime import datetime

class WorkflowContext:
    def __init__(self, session_id):
        self.session_id = session_id
        self.stop_event = asyncio.Event()
        self.started_at = datetime.utcnow()
        self.workflow_id = str(uuid.uuid4())

    def cancel(self):
        self.stop_event.set()

class WorkflowSessionManager:
    def __init__(self):
        self.sessions = {}

    def create(self, session_id: str) -> WorkflowContext:
        context = WorkflowContext(session_id)
        self.sessions[session_id] = context
        return context

    def get(self, session_id: str) -> WorkflowContext:
        return self.sessions.get(session_id)

    def stop(self, session_id: str):
        ctx = self.sessions.get(session_id)
        if ctx:
            ctx.cancel()

    def remove(self, session_id: str):
        self.sessions.pop(session_id, None)

workflow_sessions = WorkflowSessionManager() 
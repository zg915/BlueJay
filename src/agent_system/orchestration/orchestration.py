"""
Pure orchestration coordinator for agent workflow management
Handles agent handoffs and streaming without business logic
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent

from ..agents import CertificationAgent, AnswerAgent, FlashcardAgent, TriageAgent
from ..guardrails import validate_input, input_moderation, output_moderation
from src.services.database_service import (
    db_store_message, db_get_recent_context
)
from .streaming import AnswerStreamer, FlashcardStreamer
from . import operations


class WorkflowOrchestrator:
    def __init__(self):
        print("🔧 Initializing WorkflowOrchestrator...")
        
        # Set the global orchestrator for tools to access
        from ..tools.core import set_global_orchestrator
        set_global_orchestrator(self)
        
        # Initialize db as None - will be set during request processing
        self.db = None
        
        # Initialize specialized agents first
        self.certification_agent = CertificationAgent(self)
        self.answer_agent = AnswerAgent(self)
        
        # Initialize triage agent with handoffs to specialized agents
        self.triage_agent = TriageAgent(self.certification_agent, self.answer_agent)
        
        # Operations are now plain functions - no initialization needed
        
        print("✅ WorkflowOrchestrator initialized successfully")
    

    async def handle_user_question(self, session_id: str, message: str, db: AsyncSession, context=None):
        """
        Main workflow orchestration: pre-hooks → triage agent (with handoffs) → workflow agent → true agent streaming
        """
        print(f"\n🚀 Starting workflow for session: {session_id}")
        print(f"📝 User message: {message}")
        self.db = db

        try:
            print("🔍 Running pre-hooks...")
            validate_input(message)
            print("✅ Input validation passed")
            user_message_obj = await db_store_message(db, session_id, message, role="user")
            yield {"type": "user_message", "response": user_message_obj}
            print("✅ Message stored in database")
            user_message_id = getattr(user_message_obj, 'message_id', None)
            if input_moderation(message):
                assistant_message_obj = await db_store_message(db, session_id, "Sorry, I cannot help with harmful queries", role="assistant", reply_to=user_message_id)
                yield {"type": "harmful", "response": "Sorry, I cannot help with harmful queries"}
                yield {"type": "completed", "response": assistant_message_obj}
                return
            print("✅ Input moderation passed")
            context_data = await db_get_recent_context(db, session_id, 9)
            print(f"📚 Retrieved last {context_data.get('message_count', 0)} messages")
            print("\n🎯 Running triage agent with handoffs...")

            result = Runner.run_streamed(
                starting_agent=self.triage_agent,
                input=context_data.get("messages", [])
            )

            # Parsers
            answer_streamer = AnswerStreamer()
            flashcard_streamer = FlashcardStreamer()
            global_buf = ""
            text_response = []
            is_cancelled = False
            certification_response = []
            async for event in result.stream_events():

                # Check for cancellation
                if context and context.stop_event.is_set():
                    print(f"🛑 Workflow cancelled by frontend.")
                    yield {"type": "cancelled", "message": "Response cancelled by User"}
                    text_response.append("Response cancelled by User")
                    is_cancelled = True
                    break

                # 1) Agent handoff
                if event.type == "agent_updated_stream_event":
                    current_agent = event.new_agent
                    yield {"type": "processing", "response": f"Handing to {current_agent.name}"}
                    if current_agent is self.certification_agent:
                        yield {"type": "format", "response": "List"}
                    elif current_agent is self.answer_agent:
                        yield {"type": "format", "response": "Answer"}
                    continue

                # 2) Tool use trigger
                if event.type == "run_item_stream_event" and event.name == "tool_called":
                    item = event.item
                    tool = item.raw_item.name
                    yield {"type": "processing", "response": f"Performing {tool}"}
                    continue

                # 3) Stream ONLY inside "answer" string and "flashcards" array
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    chunk = event.data.delta
                    prev_len = len(global_buf)
                    global_buf += chunk

                    # Answer chunks
                    for txt in answer_streamer.feed(global_buf, prev_len):
                        yield {"type": "answer_chunk", "response": txt}
                        text_response.append(txt)

                    # Flashcards
                    for card in flashcard_streamer.feed(global_buf, prev_len, chunk):
                        yield {"type": "flashcard", "response": card}
                        certification_response.append(card)

                    continue

            #Save the finalized message
            if not certification_response:
                certification_response = None
            assistant_message_obj = await db_store_message(db, session_id, "".join(text_response), certifications=certification_response, role="assistant", reply_to=user_message_id, is_cancelled=is_cancelled)
            yield {"type": "completed", "response": assistant_message_obj}
            return

        except Exception as e:
            print(f"❌ Error in handle_user_question: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            yield {"error": str(e)}
            return
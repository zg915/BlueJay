"""
Pure orchestration coordinator for agent workflow management
Handles agent handoffs and streaming without business logic
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from agents import Runner
from openai.types.responses import ResponseTextDeltaEvent
from langfuse import get_client

from ..agents import CertificationAgent, AnswerAgent, TriageAgent
from ..guardrails import validate_input, input_moderation
from src.services.database_service import (
    db_store_message, db_get_recent_context
)
from .streaming import AnswerStreamer, FlashcardStreamer
from . import operations


class WorkflowOrchestrator:
    def __init__(self):
        print("🔧 Initializing WorkflowOrchestrator...")
        
        # Initialize db as None - will be set during request processing
        self.db = None
        
        # Initialize specialized agents first
        self.certification_agent = CertificationAgent()
        self.answer_agent = AnswerAgent()
        
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
            #TODO: add back full context
            context_data = await db_get_recent_context(db, session_id, 1)
            print(f"📚 Retrieved last {context_data.get('message_count', 0)} messages")
            print("\n🎯 Running triage agent with handoffs...")

            # Create Langfuse span 
            langfuse = get_client()
            with langfuse.start_as_current_span(name="Agent Workflow") as span:
                
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
                # Track tool calls to match with tool outputs
                tool_call_map = {}
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

                    # 2) Tool use trigger - stream when tool is called and map call_id
                    # NOTE: Due to OpenAI Agents SDK bug #1282, these events fire late (after tool execution)
                    # This will be fixed in a future SDK release
                    if event.type == "run_item_stream_event" and hasattr(event.item, 'type'):
                        
                        if event.item.type == "tool_call_item":
                            # Get tool name and call_id for mapping
                            raw_item = getattr(event.item, 'raw_item', None)
                            
                            # Raw item is a ResponseFunctionToolCall object, not a dict
                            tool_name = getattr(raw_item, 'name', None) if raw_item else None
                            call_id = getattr(raw_item, 'call_id', None) if raw_item else None
                            
                            if tool_name and call_id:
                                # Store the mapping for later correlation
                                tool_call_map[call_id] = tool_name
                                yield {"type": "processing", "response": f"Performing {tool_name}"}
                            continue
                        
                        elif event.item.type == "tool_call_output_item":
                            # Get call_id and look up the tool name
                            raw_item = getattr(event.item, 'raw_item', None)
                            
                            # Raw item is a dict for output items
                            call_id = raw_item.get('call_id') if isinstance(raw_item, dict) else None
                            tool_name = tool_call_map.get(call_id, 'unknown') if call_id else 'unknown'
                            
                            # Get the output
                            output = raw_item.get('output', '') if isinstance(raw_item, dict) else ''
                            
                            if tool_name == "prepare_flashcard":
                                try:
                                    import json
                                    # If output is already a dict/list, convert it to JSON string first
                                    if isinstance(output, (dict, list)):
                                        result_data = output
                                    else:
                                        result_data = json.loads(str(output))
                                    yield {"type": "tool_result", "response": result_data}
                                except json.JSONDecodeError:
                                    yield {"type": "tool_result", "response": str(output)}
                            continue

                    # 4) Stream ONLY inside "answer" string and "flashcards" array
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

                # Update trace once with all information
                span.update_trace(
                    input=context_data.get("messages", []),
                    output={"response": "".join(text_response), "certifications": certification_response},
                    session_id=session_id,
                    tags=["Main"]
                )
            print("✅ Agent answer completed")
            #Save the finalized message
            if not certification_response:
                certification_response = None
            else:
                for card in certification_response:
                        asyncio.create_task(
                            operations.run_compliance_agent_background(str(card))
                            )
            assistant_message_obj = await db_store_message(db, session_id, "".join(text_response), certifications=certification_response, role="assistant", reply_to=user_message_id, is_cancelled=is_cancelled)
            print("✅ Message stored in database")
            yield {"type": "completed", "response": assistant_message_obj}
            return

        except Exception as e:
            print(f"❌ Error in handle_user_question: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            yield {"error": str(e)}
            return
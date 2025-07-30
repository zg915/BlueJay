"""
Orchestration agent for routing requests to specialized agents
"""

import json
from json.decoder import scanstring
import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from agents import Agent, handoff, ItemHelpers, Runner
from openai.types.responses import ResponseTextDeltaEvent, ResponseFunctionCallArgumentsDeltaEvent
from .agents import CertificationAgent, AnswerAgent, FlashcardAgent, TriageAgent
from src.agent_system.guardrails import validate_input, input_moderation, output_moderation
from src.agent_system.internal import (
    store_message_db, store_final_response_db, store_research_request_db,
    get_recent_context_db, store_context_db
)

import asyncio
import re




# -------- Minimal stream parsers --------
class AnswerStreamer:
    """Stream a single JSON string value for key "answer"."""
    KEY = '"answer"'

    def __init__(self):
        self.in_answer = False
        self.finished = False
        self.start_idx = -1   # index of first char INSIDE the string
        self.stream_pos = 0   # how many chars from the answer we've emitted

    @staticmethod
    def _find_start(buf: str, search_from: int) -> int:
        k = buf.find(AnswerStreamer.KEY, search_from)
        if k == -1:
            return -1
        colon = buf.find(":", k + len(AnswerStreamer.KEY))
        if colon == -1:
            return -1
        q = buf.find('"', colon + 1)
        return -1 if q == -1 else q + 1

    @staticmethod
    def _scan_to_close(buf: str, start: int):
        """
        Scan forward from `start` (inside a JSON string) until we find the closing quote.
        Returns (end_pos_exclusive, raw_piece, finished_bool).
        raw_piece is the newly available raw substring (without closing quote).
        """
        i = start
        escaped = False
        while i < len(buf):
            c = buf[i]
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                return i + 1, buf[start:i], True
            i += 1
        return i, buf[start:], False

    def feed(self, global_buf: str, prev_len: int):
        """Yield decoded text chunks as they become available."""
        if self.finished:
            return []
        out = []

        # enter answer mode if not yet
        if not self.in_answer:
            start = self._find_start(global_buf, 0)  # search entire buffer for robustness
            if start != -1:
                self.in_answer = True
                self.start_idx = start
                self.stream_pos = 0

        # if inside answer, stream what's new
        if self.in_answer:
            abs_pos = self.start_idx + self.stream_pos
            if abs_pos < len(global_buf):
                end_pos, raw_piece, done = self._scan_to_close(global_buf, abs_pos)
                if raw_piece:
                    try:
                        out.append(json.loads(f'"{raw_piece}"'))
                    except Exception:
                        out.append(raw_piece)
                    self.stream_pos += len(raw_piece)
                if done:
                    self.in_answer = False
                    self.finished = True
                    self.stream_pos += 1  # closing quote
        return out


class FlashcardStreamer:
    """Stream objects inside the JSON array under key "flashcards" using a raw_decode loop."""
    KEY = '"flashcards"'

    def __init__(self):
        self.started = False
        self.done = False
        self.buf = ""                  # everything after the '[' of the array
        self.decoder = json.JSONDecoder()

    @staticmethod
    def _find_array_lb(buf: str, search_from: int) -> int:
        k = buf.find(FlashcardStreamer.KEY, search_from)
        if k == -1:
            return -1
        lb = buf.find("[", k)
        return lb

    def _extract(self):
        """Return list of parsed objs, update self.buf, and set done when ']' hit."""
        out = []
        s = self.buf.lstrip(", \n")
        while s:
            # array end?
            if s and s[0] == ']':
                self.done = True
                s = s[1:]  # drop the ']'
                break
            # not starting at object? skip one char
            if s and s[0] != '{':
                s = s[1:]
                continue
            # try to decode one object
            try:
                obj, consumed = self.decoder.raw_decode(s)
            except ValueError:
                # need more data
                break
            out.append(obj)
            s = s[consumed:].lstrip(", \n")
        self.buf = s
        return out

    def feed(self, global_buf: str, prev_len: int, new_chunk: str):
        """Yield flashcard dicts as they complete."""
        if self.done:
            return []

        out = []
        # detect start of array once
        if not self.started:
            lb = self._find_array_lb(global_buf, max(0, prev_len - 64))
            if lb != -1:
                self.started = True
                # push everything after '[' into buffer
                self.buf += global_buf[lb + 1:]
                out.extend(self._extract())
                return out

        # if already started, just append the new chunk and parse
        if self.started and not self.done:
            self.buf += new_chunk
            out.extend(self._extract())

        return out

class WorkflowOrchestrator:
    def __init__(self):
        print("🔧 Initializing WorkflowOrchestrator...")
        
        # Set the global orchestrator for tools to access
        from src.agent_system.tools.core import set_global_orchestrator
        set_global_orchestrator(self)
        
        # Initialize db as None - will be set during request processing
        self.db = None
        
        # Initialize specialized agents first
        self.certification_agent = CertificationAgent(self)
        self.answer_agent = AnswerAgent(self)
        
        # Initialize triage agent with handoffs to specialized agents
        self.triage_agent = TriageAgent(self.certification_agent, self.answer_agent)
        
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
            user_message_obj = await store_message_db(session_id, message, db, "user")
            yield {"type": "user_message", "response": user_message_obj}
            print("✅ Message stored in database")
            user_message_id = getattr(user_message_obj, 'message_id', None)
            if input_moderation(message):
                assistant_message_obj = await store_message_db(session_id, "Sorry, I cannot help with harmful queries", db, "assistant", reply_to=user_message_id)
                yield {"type": "harmful", "response": "Sorry, I cannot help with harmful queries"}
                yield {"type": "completed", "response": assistant_message_obj}
                return
            print("✅ Input moderation passed")
            context_data = await get_recent_context_db(db, session_id, 3)
            print(f"📚 Retrieved last {context_data.get('message_count', 0)} messages")
            print("\n🎯 Running triage agent with handoffs...")

            # summary_memory = context["summary"]

            result = Runner.run_streamed(
                starting_agent=self.triage_agent,
                input=message
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
            assistant_message_obj = await store_message_db(session_id, "".join(text_response), db, "assistant", certifications=certification_response,reply_to=user_message_id, is_cancelled = is_cancelled)
            yield {"type": "completed", "response": assistant_message_obj}
            return

        except Exception as e:
            print(f"❌ Error in handle_user_question: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            yield {"error": str(e)}
            return
        
    async def compliance_research(self, search_queries: list[str]):
        """
        Specialized workflow for compliance requests.
        Runs RAG, Web, and DB search for each query in parallel, then combines and returns all results.
        """
        print(f"📋 Starting compliance workflow for: {search_queries}")

        # Launch 3 tasks per query (RAG, Web, DB)
        tasks = []
        try:
            #TODO: change to full queries
            for query in search_queries[:1]:
                print(f"🚀 Starting Domain_web_search: {query}")
                print(f"🚀 Starting web_search: {query}")
                tasks.append(self.web_search(query, use_domain = True))
                tasks.append(self.web_search(query, use_domain = False))
                #TODO: add the RAG
                # tasks.append(self._lookup_past_certifications(query))
            
            start_time = time.time()
            all_task_results = await asyncio.gather(*tasks, return_exceptions=True)
            total_duration = time.time() - start_time
            print(f"✅ All parallel tasks completed in {total_duration:.2f}s")

            print("📤 Returning all results (including errors) for agent processing...")
            return all_task_results
        except Exception as e:
            print(f"❌ Error in compliance_research: {e}")
    
    async def search_relevant_certification(self, search_queries: list[str]):
        """
        Specialized workflow for certification list requests.
        Runs RAG, Web, and DB search for each query in parallel, then combines and returns all results.
        """
        print(f"📋 Starting certification list workflow for: {search_queries}")

        # Launch 3 tasks per query (RAG, Web, DB)
        tasks = []
        try:
            #TODO: change back to full queries
            for query in search_queries[:1]:
                print(f"🚀 Starting Domain_web_search: {query}")
                print(f"🚀 Starting web_search: {query}")
                tasks.append(self.certification_web_search(query, use_domain = True))
                tasks.append(self.certification_web_search(query, use_domain = False))
                #TODO: add the RAG
                # tasks.append(self._lookup_past_certifications(query))
            
            start_time = time.time()  
            all_task_results = await asyncio.gather(*tasks, return_exceptions=True)
            total_duration = time.time() - start_time
            print(f"✅ All parallel tasks completed in {total_duration:.2f}s")

            print("📤 Returning all results (including errors) for agent processing...")
            return all_task_results
        except Exception as e:
            print(f"❌ Error in search_relevant_certification: {e}")

    async def certification_web_search(self, query: str, use_domain: bool = False):
        """RAG API + Domain Search: Get domain metadata and search with domain filter"""
        from src.agent_system.internal import _domain_search_kb, _perplexity_certification_search
        try:
            if use_domain:
                domains = await _domain_search_kb(query)
            else:
                domains = None

            result = await _perplexity_certification_search(query, domains)
            return result
            
        except Exception as e:
            print(f"❌ domain web search failed: {e}")
            return {}
    
    async def web_search(self, query: str, use_domain: bool = False):
        """RAG API + Domain Search: Get domain metadata and search with domain filter"""
        from src.agent_system.internal import _domain_search_kb, _perplexity_search
        try:
            if use_domain:
                domains = await _domain_search_kb(query)
            else:
                domains = None

            result = await _perplexity_search(query, domains)
            return result
            
        except Exception as e:
            print(f"❌ domain web search failed: {e}")
            return {}
        
    async def prepare_flashcard(self, certification_name:str, context: str = None):
        agent = FlashcardAgent(self)

        result = await Runner.run(
            agent,
            input=str({"certification_name": certification_name, "context": context}),
        )

        return str(result.final_output)

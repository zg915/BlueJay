"""
Orchestration agent for routing requests to specialized agents
"""

import json
import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from agents import Agent, handoff
from .agents import CertificationAgent, AnswerAgent
from src.config.prompts import TRIAGE_AGENT_INSTRUCTION
from src.agent_system.guardrails import validate_input, input_moderation, output_moderation
from src.agent_system.internal import (
    store_message_db, store_final_response_db, store_research_request_db,
    get_recent_context_db, store_context_db
)

from agents import Runner
import asyncio

#TODO: move it somewhere else?
from pydantic import BaseModel, Field
from src.config.output_structure import Certifications_Structure
class ReasonArgs(BaseModel):

    reason: str = Field(
        ...,
        description=(
            "A concise and clear one sentence reason of why choosing this handoff"
        )
    )

def log_with_time(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] {message}")

async def timed_task(name, coro):
    """Wrapper to time async tasks and log start/end times"""
    start = time.time()
    start_time = datetime.now()
    log_with_time(f"🚀 START {name}")
    
    try:
        result = await coro
        end = time.time()
        end_time = datetime.now()
        duration = end - start
        log_with_time(f"✅ END {name} (duration: {duration:.2f}s)")
        
        return {
            "name": name,
            "start": start_time,
            "end": end_time,
            "duration": duration,
            "result": result,
            "status": "success"
        }
    except Exception as e:
        end = time.time()
        end_time = datetime.now()
        duration = end - start
        log_with_time(f"❌ ERROR {name} (duration: {duration:.2f}s): {e}")
        
        return {
            "name": name,
            "start": start_time,
            "end": end_time,
            "duration": duration,
            "result": None,
            "status": "error",
            "error": str(e)
        }

def print_timing_table(task_results):
    """Print a formatted table of task timings"""
    print("\n" + "="*80)
    print("📊 PARALLEL TASK TIMING TABLE")
    print("="*80)
    
    # Create table data
    table_data = []
    for task_result in task_results:
        if isinstance(task_result, dict):
            start_str = task_result["start"].strftime('%H:%M:%S.%f')[:-3]
            end_str = task_result["end"].strftime('%H:%M:%S.%f')[:-3]
            duration_str = f"{task_result['duration']:.2f}s"
            status = task_result["status"]
            
            table_data.append([
                task_result["name"],
                start_str,
                end_str,
                duration_str,
                status
            ])
        else:
            # Handle exceptions
            table_data.append([
                f"Task-{len(table_data)+1}",
                "-",
                "-",
                "-",
                "ERROR"
            ])
    
    # Print table manually (no external dependencies)
    if table_data:
        # Header
        print(f"{'Task Name':<25} {'Start Time':<15} {'End Time':<15} {'Duration':<10} {'Status':<10}")
        print("-" * 80)
        
        # Data rows
        for row in table_data:
            print(f"{row[0]:<25} {row[1]:<15} {row[2]:<15} {row[3]:<10} {row[4]:<10}")
    
    print("="*80)
    print("💡 Parallel execution confirmed! All tasks started at nearly the same time.")
    print("="*80 + "\n")

class WorkflowOrchestrator:
    def __init__(self):
        print("🔧 Initializing WorkflowOrchestrator...")
        #TODO: move it somewhere else?
        def _print_reason(context, input):
            print("\n\n\n", input, "\n\n\n")
            pass
        # Set the global orchestrator for tools to access
        from src.agent_system.tools.core import set_global_orchestrator
        set_global_orchestrator(self)
        

        # Initialize db as None - will be set during request processing
        self.db = None
        self.certification_agent = CertificationAgent(self)
        self.answer_agent = AnswerAgent(self)

        self.triage_agent = Agent(
            name="Triage agent",
            model="gpt-4o",
            instructions=TRIAGE_AGENT_INSTRUCTION,
            #TODO: handle the filter input
            handoffs=[
                handoff(self.certification_agent,
                        tool_name_override="transfer_to_certification_workflow",
                        input_type=ReasonArgs,
                        on_handoff=_print_reason),
                handoff(self.answer_agent,
                        input_type=ReasonArgs,
                        on_handoff=_print_reason)
            ]
        )
        print("✅ WorkflowOrchestrator initialized successfully")

    async def handle_user_question(self, session_id: str, message: str, db: AsyncSession):
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
            print("✅ Message stored in database")
            message_id = getattr(user_message_obj, 'message_id', None)
            input_moderation(message)
            print("✅ Input moderation passed")
            context = await get_recent_context_db(db, session_id, 3)
            print(f"📚 Retrieved last {context.get('message_count', 0)} messages")
            print("\n🎯 Running triage agent with handoffs...")
            summary_memory = context["summary"]

            # Use true agent streaming
            result = Runner.run_streamed(
                starting_agent=self.triage_agent,
                input=message
            )
            async for event in result.stream_events():
                output = None
                if event.type == "run_item_stream_event":
                    item = event.item
                    # Message output
                    if getattr(item, 'type', None) == "message_output_item":
                        from agents import ItemHelpers
                        output = ItemHelpers.text_message_output(item)
                    # Tool output
                    elif getattr(item, 'type', None) == "tool_call_output_item":
                        output = getattr(item, 'output', None)

                if output is not None:
                    # Handle JSON strings
                    if isinstance(output, str):
                        try:
                            output = json.loads(output)
                        except Exception:
                            pass  # Not JSON, keep as string

                    # Handle CertificationAgent output (Certifications_Structure or dict with certifications)
                    if isinstance(output, Certifications_Structure):
                        for cert in output.certifications:
                            yield cert
                    elif isinstance(output, dict):
                        # Check for nested certifications structure
                        if 'certifications' in output:
                            certs = output['certifications']
                            if isinstance(certs, dict) and 'certifications' in certs:
                                certs = certs['certifications']
                            if isinstance(certs, list):
                                for cert in certs:
                                    yield cert
                                continue
                        # Check for list of certifications in any key
                        for key, value in output.items():
                            if isinstance(value, list) and len(value) > 0:
                                if all(isinstance(item, dict) and 'certificate_name' in item for item in value):
                                    for cert in value:
                                        yield cert
                                    continue
                    # Handle AnswerAgent output (formatted text)
                    elif isinstance(output, str):
                        yield output
                    # Handle other outputs as-is
                    else:
                        yield output

        except Exception as e:
            print(f"❌ Error in handle_user_question: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            yield {"error": str(e)}


 
    async def handle_general_research_workflow(self, enhanced_query: str, context: dict, db: AsyncSession):
        """
        General research workflow for non-certification requests.
        """
        print(f"🔬 Starting general research workflow for: {enhanced_query}")
        
        # Execute all three search types in parallel with timing
        log_with_time("🚀 Starting parallel search operations...")
        all_results = await asyncio.gather(
            timed_task("RAG-Domain", self._domain_web_search(enhanced_query)),
            timed_task("General-Web", self._general_web_search(enhanced_query)),
            # timed_task("Internal-DB", self._lookup_past_certifications(enhanced_query, db)),
            return_exceptions=True
        )
        
        # Print timing table
        print_timing_table(all_results)
        
        # Extract results from timed task results
        rag_task_result = all_results[0] if not isinstance(all_results[0], Exception) else {"result": [], "status": "error"}
        general_task_result = all_results[1] if not isinstance(all_results[1], Exception) else {"result": [], "status": "error"}
        db_task_result = all_results[2] if not isinstance(all_results[2], Exception) else {"result": [], "status": "error"}
        rag_domain_results = rag_task_result.get("result", []) if isinstance(rag_task_result, dict) else []
        general_results = general_task_result.get("result", []) if isinstance(general_task_result, dict) else []
        db_results = db_task_result.get("result", []) if isinstance(db_task_result, dict) else []
            
        # Log results from each parallel task
        print(f"\n📊 PARALLEL TASK RESULTS:")
        print(f"    🔍 RAG Domain Search Results: {len(rag_domain_results) if not isinstance(rag_domain_results, Exception) else 'ERROR'} items")
        if not isinstance(rag_domain_results, Exception):
            for i, result in enumerate(rag_domain_results[:3]):  # Show first 3 results
                print(f"      {i+1}. {result.get('certificate_name', 'Unknown')} - {result.get('certificate_description', 'No description')[:50]}...")
            if len(rag_domain_results) > 3:
                print(f"      ... and {len(rag_domain_results) - 3} more results")
        else:
            print(f"      ❌ RAG Domain Search Error: {rag_domain_results}")
        
        print(f"    🌐 General Web Search Results: {len(general_results) if not isinstance(general_results, Exception) else 'ERROR'} items")
        if not isinstance(general_results, Exception):
            for i, result in enumerate(general_results[:3]):  # Show first 3 results
                print(f"      {i+1}. {result.get('certificate_name', 'Unknown')} - {result.get('certificate_description', 'No description')[:50]}...")
            if len(general_results) > 3:
                print(f"      ... and {len(general_results) - 3} more results")
        else:
            print(f"      ❌ General Web Search Error: {general_results}")
        
        print(f"    🗄️ Internal DB Lookup Results: {len(db_results) if not isinstance(db_results, Exception) else 'ERROR'} items")
        if not isinstance(db_results, Exception):
            for i, result in enumerate(db_results[:3]):  # Show first 3 results
                print(f"      {i+1}. {result.get('certificate_name', 'Unknown')} - {result.get('certificate_description', 'No description')[:50]}...")
            if len(db_results) > 3:
                print(f"      ... and {len(db_results) - 3} more results")
        else:
            print(f"      ❌ Internal DB Lookup Error: {db_results}")
        
        print(f"📊 END PARALLEL TASK RESULTS\n")
        
        # Combine all results
        all_results = []
        if not isinstance(rag_domain_results, Exception):
            all_results.extend(rag_domain_results)
        if not isinstance(general_results, Exception):
            all_results.extend(general_results)
        if not isinstance(db_results, Exception):
            all_results.extend(db_results)
        
        print(f"✅ Combined {len(all_results)} total results from all sources")
        
        # Return raw results for OpenAI processing
        print("📤 Returning raw results for OpenAI processing...")
        return all_results
    
    async def search_relevant_certification(self, search_queries: list[str]):
        """
        Specialized workflow for certification list requests.
        Runs RAG, Web, and DB search for each query in parallel, then combines and returns all results.
        """
        print(f"📋 Starting certification list workflow for: {search_queries}")

        # Launch 3 tasks per query (RAG, Web, DB)
        tasks = []
        try:
            #TODO: change the search_queries back to all
            for query in search_queries[:1]:
                tasks.append(timed_task(f"Domain_Web_Search: {query}", self._certification_web_search(query, use_domain = True)))
                tasks.append(timed_task(f"Web_Search: {query}", self._certification_web_search(query, use_domain = False)))
                # tasks.append(timed_task(f"RAG: {query}", self._lookup_past_certifications(query)))
            all_task_results = await asyncio.gather(*tasks, return_exceptions=True)
            print_timing_table(all_task_results)

            # Flatten and collect results, tagging with source query
            all_results = {}
            for idx, task_result in enumerate(all_task_results):
                if isinstance(task_result, dict) and task_result.get("status") == "success":
                    all_results["answer_{0}".format(idx)] = task_result["result"]
            # TODO: delete the following, or figure out good ways to store
            # for idx, task_result in enumerate(all_task_results):
            #     if isinstance(task_result, dict) and task_result.get("status") == "success":
            #         # Each result is a list of dicts (certifications)
            #         # Figure out which query this result came from
            #         query_index = idx // 3
            #         source_query = search_queries[query_index] if query_index < len(search_queries) else None
            #         for item in task_result.get("result", []):
            #             # Attach the originating query for traceability
            #             if isinstance(item, dict):
            #                 item['source_query'] = source_query
            #             all_results.append(item)
            #     else:
            #         print(f"❌ Task {idx} failed or returned no results.")

            # print(f"✅ Combined {len(all_results)} total certification results from all sources/queries")
            # Optionally store results, etc.
            # await self._store_certification_result(str(all_results), search_queries, db)

            print("📤 Returning raw certification results for LLM deduplication and structuring...")
            return all_results
        except Exception as e:
            print(f"❌ Error in search_relevant_certification: {e}")

    
    
    async def _store_certification_result(self, results: str, query: str, db: AsyncSession):
        """Store certification result and metadata"""
        # TODO: Implement result storage
        # This would store the final result with metadata
        pass 

    async def _certification_web_search(self, query: str, use_domain: bool = False):
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
    
       
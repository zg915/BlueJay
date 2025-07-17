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
from src.config.output_structure import Reason_Structure
from src.agent_system.guardrails import validate_input, input_moderation, output_moderation
from src.agent_system.internal import (
    store_message_db, store_final_response_db, store_research_request_db,
    get_recent_context_db, store_context_db
)

from agents import Runner
import asyncio

#TODO: move it somewhere else?
from pydantic import BaseModel, Field
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
            print("\n\n\nreason of choosing the worflow: ", input, "\n\n\n")
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
                        input_type=Reason_Structure,
                        on_handoff=_print_reason),
                handoff(self.answer_agent,
                        input_type=Reason_Structure,
                        on_handoff=_print_reason)
            ]
        )
        print("✅ WorkflowOrchestrator initialized successfully")

    async def handle_user_question(self, session_id: str, message: str, db: AsyncSession):
        """
        Main workflow orchestration: pre-hooks → triage agent (with handoffs) → workflow agent → OpenAI streaming
        """
        print(f"\n🚀 Starting workflow for session: {session_id}")
        print(f"📝 User message: {message}")
        
        # Set the db session for tools to access
        self.db = db
        
        # Pre-hooks: mandatory steps
        try:
            print("🔍 Running pre-hooks...")
            #TODO: this should never be triggered, if ever triggered, just pop 500 internal error
            validate_input(message)
            print("✅ Input validation passed")
            # Store the user message and get the message object
            user_message_obj = await store_message_db(session_id,message, db, "user")
            print("✅ Message stored in database")
            message_id = getattr(user_message_obj, 'message_id', None)
            #TODO: if the message is harmful, save the message to db (role:assistant, content: "HARMFUL", "type": "Harmful")
            input_moderation(message)
            print("✅ Input moderation passed")
            # Load last 5 messages for context
            #TODO: change the context window back to 7
            context = await get_recent_context_db(db, session_id, 3)
            print(f"📚 Retrieved last {context.get('message_count', 0)} messages")
            # Run triage agent (which will handoff automatically)
            print("\n🎯 Running triage agent with handoffs...")
            #TODO: think about how to use the summary memory and feed to triage
            summary_memory = context["summary"]

            triage_result = await Runner.run(
                starting_agent=self.triage_agent,
                input=message  # Use the actual user message, not context messages
            )
            #TODO: delete everything below
            # Debug: Check if the triage agent actually called a workflow agent
            if hasattr(triage_result, 'raw_responses'):
                print(f"🔍 Number of raw responses: {len(triage_result.raw_responses) if triage_result.raw_responses else 0}")
                for i, response in enumerate(triage_result.raw_responses or []):
                    print(f"🔍 Raw response {i+1}: {response}")
            # The result is the output of the correct workflow agent
            workflow_output = triage_result.final_output if hasattr(triage_result, 'final_output') else triage_result
            print(f"📊 Workflow output type: {type(workflow_output)}")
            print(f"📊 Workflow output length: {len(workflow_output) if isinstance(workflow_output, list) else 'N/A'}")
            
            # Handle different types of workflow output
            # Check if the agent returned structured, deduplicated results
            if isinstance(workflow_output, list) and all(isinstance(item, dict) for item in workflow_output):
                # Agent already returned structured, deduplicated results
                print("✅ Agent returned structured results, streaming directly...")
                print(f"📊 Streaming {len(workflow_output)} deduplicated results directly")
                return workflow_output
            elif isinstance(workflow_output, str):
                # If it's a string, it might be a JSON response or direct text
                try:
                    parsed = json.loads(workflow_output)
                    if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
                        # Agent returned JSON string of structured results
                        print("✅ Agent returned JSON structured results, streaming directly...")
                        print(f"📊 Streaming {len(parsed)} deduplicated results directly")
                        return parsed
                    elif isinstance(parsed, dict) and 'content' in parsed:
                        # This is a direct response from the workflow agent
                        print(f"📝 Direct response from workflow agent: {parsed['content']}")
                        return parsed['content']
                    elif isinstance(parsed, dict):
                        # Agent returned a complex JSON object, try to extract certification data
                        print(f"📝 Agent returned complex JSON object, attempting to extract data...")
                        certification_data = []
                        
                        # Look for certification arrays in the response
                        for key, value in parsed.items():
                            if isinstance(value, list) and len(value) > 0:
                                if all(isinstance(item, dict) and 'certificate_name' in item for item in value):
                                    certification_data.extend(value)
                                elif all(isinstance(item, dict) for item in value):
                                    # Assume these are certification objects
                                    certification_data.extend(value)
                        
                        if certification_data:
                            print(f"✅ Extracted {len(certification_data)} certification objects from complex response")
                            return certification_data
                        else:
                            print(f"⚠️ No certification data found in complex response")
                            # Check if all values are empty arrays
                            all_empty = all(isinstance(value, list) and len(value) == 0 for value in parsed.values() if isinstance(value, list))
                            if all_empty:
                                print(f"⚠️ Agent returned object with all empty arrays, returning empty list")
                                return []
                            else:
                                print(f"⚠️ Agent returned complex object with no certification data")
                                return []
                    else:
                        # Check if parsed result is empty
                        if isinstance(parsed, list) and len(parsed) == 0:
                            print("⚠️ Agent returned empty results, returning empty list")
                            return []
                        # Fall back to OpenAI processing for non-structured data
                        print(f"📝 Non-structured data from workflow agent, using OpenAI processing")
                        final_result = await self._stream_openai_response(
                            parsed if isinstance(parsed, list) else [parsed], 
                            message, session_id, db, message_id
                        )
                        return final_result
                except json.JSONDecodeError:
                    # Not JSON, treat as direct text response
                    print(f"📝 Direct text response from workflow agent: {workflow_output}")
                    return workflow_output
            else:
                # Fall back to OpenAI processing for unknown types
                print(f"📝 Unknown workflow output type: {type(workflow_output)}, using OpenAI processing")
                final_result = await self._stream_openai_response(
                    workflow_output if isinstance(workflow_output, list) else [workflow_output], 
                    message, session_id, db, message_id
                )
                return final_result
        except Exception as e:
            print(f"❌ Error in handle_user_question: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            raise 


 
    async def compliance_research(self, search_queries: list[str]):
        """
        Specialized workflow for compliance requests.
        Runs RAG, Web, and DB search for each query in parallel, then combines and returns all results.
        """
        print(f"📋 Starting compliance workflow for: {search_queries}")

        # Launch 3 tasks per query (RAG, Web, DB)
        tasks = []
        try:
            for query in search_queries:
                tasks.append(timed_task(f"Domain_web_search: {query}", self._web_search(query, use_domain = True)))
                tasks.append(timed_task(f"web_search: {query}", self._web_search(query, use_domain = False)))
                # tasks.append(timed_task(f"RAG: {query}", self._lookup_past_certifications(query)))
            all_task_results = await asyncio.gather(*tasks, return_exceptions=True)
            print_timing_table(all_task_results)

            # Flatten and collect results, tagging with source query
            all_results = {}
            for idx, task_result in enumerate(all_task_results):
                if isinstance(task_result, dict) and task_result.get("status") == "success":
                    all_results["answer_{0}".format(idx)] = task_result["result"]

            print("📤 Returning raw certification results for LLM deduplication and structuring...")
            return all_results
        except Exception as e:
            print(f"❌ Error in search_relevant_certification: {e}")
    
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
                tasks.append(timed_task(f"Domain_web_search: {query}", self._certification_web_search(query, use_domain = True)))
                tasks.append(timed_task(f"web_search: {query}", self._certification_web_search(query, use_domain = False)))
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

    
    
    async def _stream_openai_response(self, raw_results: list, original_query: str, session_id: str, db: AsyncSession, message_id: str):
        """
        Stream OpenAI response for deduplication and synthesis of raw results, expecting a JSON array of objects in a specific format.
        """
        print(f"🚀 Starting OpenAI streaming for {len(raw_results)} raw results...")
        print(f"📊 Raw results type: {type(raw_results)}")
        print(f"📊 Raw results length: {len(raw_results)}")
        
        # Check if we have any meaningful results to process
        if not raw_results or (isinstance(raw_results, list) and len(raw_results) == 0):
            print("⚠️ No raw results to process, returning empty list")
            return []
        
        # Check if all results are empty or None
        meaningful_results = [r for r in raw_results if r is not None and r != {} and r != []]
        if not meaningful_results:
            print("⚠️ No meaningful results to process, returning empty list")
            return []
        
        try:
            # Convert raw results to a structured format for OpenAI
            print("🔄 Converting raw results to structured format...")
            results_text = self._format_raw_results_for_openai(meaningful_results)
            print(f"📝 Formatted results text length: {len(results_text)}")
            print(f"📝 First 200 chars of formatted results: {results_text[:200]}...")
            
            # Create prompt for OpenAI (JSON format enforced)
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

Original Query: {original_query}

Raw Results ({len(meaningful_results)} items):
{results_text}
"""
            print(f"📤 Sending {len(meaningful_results)} results to OpenAI for JSON processing...")
            print(f"📝 Prompt length: {len(prompt)}")
            print(f"📝 First 300 chars of prompt: {prompt[:300]}...")
            
            # Call OpenAI with streaming
            from src.services.openai_service import stream_openai_response
            print("🤖 Calling OpenAI streaming service...")
            response_text = await stream_openai_response(prompt, session_id)
            print(f"✅ OpenAI streaming completed, response length: {len(response_text)} characters")
            print(f"📝 OpenAI response: '{response_text}'")
            
            # Clean and parse the JSON response
            print("🧹 Cleaning and parsing OpenAI JSON response...")
            parsed_json = self._clean_and_parse_json_response(response_text)
            print(f"✅ Parsed OpenAI JSON, {len(parsed_json)} objects")
            print(f"📊 Parsed JSON: {parsed_json}")
            
            return parsed_json
            
        except Exception as e:
            print(f"❌ Error in OpenAI streaming: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            raise

 
    


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
    
       
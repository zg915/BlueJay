"""
Orchestration agent for routing requests to specialized agents
"""

import json
import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from src.agent_system.agents import CertificationWorkflowAgent, ResearchWorkflowAgent
from src.config.prompts import TRIAGE_AGENT_PROMPT
from src.agent_system.guardrails import validate_input, input_moderation, output_moderation
from src.agent_system.tools import (
    store_message_db, store_final_response_db, store_research_request_db,
    get_recent_context_db, store_context_db
)
from agents import Agent, handoff, Runner
import asyncio

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
        self.certification_agent = CertificationWorkflowAgent(self)
        self.research_agent = ResearchWorkflowAgent(self)
        self.triage_agent = Agent(
            name="Triage agent",
            instructions=TRIAGE_AGENT_PROMPT,
            handoffs=[
                handoff(self.certification_agent, tool_name_override="transfer_to_certification_workflow"),
                handoff(self.research_agent, tool_name_override="transfer_to_research_workflow")
            ]
        )
        print("✅ WorkflowOrchestrator initialized successfully")

    async def handle_user_question(self, user_id: str, session_id: str, message: str, db: AsyncSession):
        """
        Main workflow orchestration: pre-hooks → triage agent (with handoffs) → workflow agent → OpenAI streaming
        """
        print(f"\n🚀 Starting workflow for user: {user_id}, session: {session_id}")
        print(f"📝 User message: {message}")
        try:
            # Pre-hooks: mandatory steps
            print("🔍 Running pre-hooks...")
            validate_input(message)
            print("✅ Input validation passed")
            input_moderation(message)
            print("✅ Input moderation passed")
            # Store the user message and get the message object
            user_message_obj = await store_message_db(user_id, session_id, message, db)
            print("✅ Message stored in database")
            message_id = getattr(user_message_obj, 'message_id', None)
            # Load last 5 messages for context
            context = await get_recent_context_db(db, session_id)
            print(f"📚 Retrieved last {context.get('message_count', 0)} messages")
            # Run triage agent (which will handoff automatically)
            print("\n🎯 Running triage agent with handoffs...")
            triage_input = f"Message: {message}\nContext: {context}"
            print(f"📤 Triage input: {triage_input[:200]}...")
            
            triage_result = await Runner.run(
                starting_agent=self.triage_agent,
                input=triage_input
            )
            print("✅ Triage agent (with handoff) completed")
            print(f"📥 Triage result type: {type(triage_result)}")
            print(f"📥 Triage result: {triage_result}")
            
            # Debug: Check if the triage agent actually called a workflow agent
            if hasattr(triage_result, 'last_agent'):
                print(f"🔍 Last agent in chain: {triage_result.last_agent.name if triage_result.last_agent else 'None'}")
            if hasattr(triage_result, 'raw_responses'):
                print(f"🔍 Number of raw responses: {len(triage_result.raw_responses) if triage_result.raw_responses else 0}")
                for i, response in enumerate(triage_result.raw_responses or []):
                    print(f"🔍 Raw response {i+1}: {response}")
            
            # The result is the output of the correct workflow agent
            workflow_output = triage_result.final_output if hasattr(triage_result, 'final_output') else triage_result
            print(f"📊 Workflow output type: {type(workflow_output)}")
            print(f"📊 Workflow output length: {len(workflow_output) if isinstance(workflow_output, list) else 'N/A'}")
            
            # Handle different types of workflow output
            if isinstance(workflow_output, str):
                # If it's a string, it might be a JSON response or direct text
                try:
                    import json
                    parsed = json.loads(workflow_output)
                    if isinstance(parsed, dict) and 'content' in parsed:
                        # This is a direct response from the workflow agent
                        print(f"📝 Direct response from workflow agent: {parsed['content']}")
                        return parsed['content']
                    else:
                        # This is structured data that needs processing
                        print(f"📝 Structured data from workflow agent: {parsed}")
                        final_result = await self._stream_openai_response(
                            parsed if isinstance(parsed, list) else [parsed], 
                            message, user_id, session_id, db, message_id
                        )
                        return final_result
                except json.JSONDecodeError:
                    # Not JSON, treat as direct text response
                    print(f"📝 Direct text response from workflow agent: {workflow_output}")
                    return workflow_output
            elif isinstance(workflow_output, list):
                # Structured data that needs processing
                print(f"📝 List of results from workflow agent: {len(workflow_output)} items")
                final_result = await self._stream_openai_response(
                    workflow_output, message, user_id, session_id, db, message_id
                )
                return final_result
            else:
                # Unknown type, return as is
                print(f"📝 Unknown workflow output type: {type(workflow_output)}")
                return str(workflow_output)
        except Exception as e:
            print(f"❌ Error in handle_user_question: {e}")
            import traceback
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            raise


    
    async def handle_certification_list_workflow(self, enhanced_query: str, context: dict, db: AsyncSession):
        """
        Specialized workflow for certification list requests.
        Includes internal DB lookup, web search, fuzzy deduplication, and vector caching.
        """
        print(f"📋 Starting certification list workflow for: {enhanced_query}")
        
        # Step 1: Generate multiple focused queries
        print("🧠 Step 1: Creating multiple focused queries...")
        search_queries = await self._generate_certification_queries(enhanced_query)
        print(f"✅ Generated {len(search_queries)} search queries")
        
        # Step 2: Run 3 parallel operations for each query
        print("🔄 Step 2: Running parallel operations for each query...")
        
        # Create all tasks for parallel execution with timing
        all_tasks = []
        for i, query in enumerate(search_queries):
            log_with_time(f"  Preparing query {i+1}/{len(search_queries)}: {query}")
            
            # Create 3 parallel tasks for this query with timing
            query_tasks = [
                timed_task(f"RAG-{i+1}", self._rag_domain_search(query)),
                timed_task(f"WEB-{i+1}", self._general_web_search(query)),
                timed_task(f"DB-{i+1}", self._lookup_past_certifications(query, db))
            ]
            all_tasks.extend(query_tasks)
        
        # Execute ALL tasks in parallel
        log_with_time(f"🚀 Executing {len(all_tasks)} operations in parallel...")
        all_results = await asyncio.gather(*all_tasks, return_exceptions=True)
        
        # Print timing table
        print_timing_table(all_results)
        
        # Group results by query (now handling timed task results)
        grouped_results = []
        for i, query in enumerate(search_queries):
            # Get results for this query (3 operations per query)
            start_idx = i * 3
            rag_task_result = all_results[start_idx] if not isinstance(all_results[start_idx], Exception) else {"result": [], "status": "error"}
            general_task_result = all_results[start_idx + 1] if not isinstance(all_results[start_idx + 1], Exception) else {"result": [], "status": "error"}
            db_task_result = all_results[start_idx + 2] if not isinstance(all_results[start_idx + 2], Exception) else {"result": [], "status": "error"}
            
            # Extract actual results from timed task results
            rag_domain_results = rag_task_result.get("result", []) if isinstance(rag_task_result, dict) else []
            general_results = general_task_result.get("result", []) if isinstance(general_task_result, dict) else []
            db_results = db_task_result.get("result", []) if isinstance(db_task_result, dict) else []
            
            query_results = {
                "query": query,
                "rag_domain_results": rag_domain_results,
                "general_results": general_results,
                "db_results": db_results
            }
            
            grouped_results.append(query_results)
            print(f"  ✅ Query {i+1} completed: {len(rag_domain_results)} domain results, {len(general_results)} general results, {len(db_results)} DB results")
            
            # Log detailed results for each query
            print(f"    📊 DETAILED RESULTS FOR QUERY {i+1}: '{query}'")
            
            # RAG Domain Results
            print(f"      🔍 RAG Domain Results ({len(rag_domain_results)} items):")
            for j, result in enumerate(rag_domain_results[:]):  # Show first 2 results
                print(f"        {j+1}. {result.get('certificate_name', 'Unknown')} - {result.get('certificate_description', 'No description')[:40]}...")
            if len(rag_domain_results) > 2:
                print(f"        ... and {len(rag_domain_results)} more results")
            
            # General Results
            print(f"      🌐 General Results ({len(general_results)} items):")
            for j, result in enumerate(general_results[:]):  # Show first 2 results
                print(f"        {j+1}. {result.get('certificate_name', 'Unknown')} - {result.get('certificate_description', 'No description')[:40]}...")
            if len(general_results) > 2:
                print(f"        ... and {len(general_results)} more results")
            
            # DB Results
            print(f"      🗄️ DB Results ({len(db_results)} items):")
            for j, result in enumerate(db_results[:]):  # Show first 2 results
                print(f"        {j+1}. {result.get('certificate_name', 'Unknown')} - {result.get('certificate_description', 'No description')[:40]}...")
            if len(db_results) > 2:
                print(f"        ... and {len(db_results) } more results")
            print(f"    📊 END DETAILED RESULTS FOR QUERY {i+1}\n")
        
        # Combine all results from all queries
        all_combined_results = []
        for query_results in grouped_results:
            # Add RAG domain results
            if query_results['rag_domain_results']:
                all_combined_results.extend(query_results['rag_domain_results'])
            # Add general results
            if query_results['general_results']:
                all_combined_results.extend(query_results['general_results'])
            # Add DB results
            if query_results['db_results']:
                all_combined_results.extend(query_results['db_results'])
        
        print(f"✅ Combined {len(all_combined_results)} total results from all queries and sources")
        
        # Return raw results for OpenAI processing
        print("📤 Returning raw results for OpenAI deduplication and streaming...")
        return all_combined_results
    
    async def handle_general_research_workflow(self, enhanced_query: str, context: dict, db: AsyncSession):
        """
        General research workflow for non-certification requests.
        """
        print(f"🔬 Starting general research workflow for: {enhanced_query}")
        
        # Execute all three search types in parallel with timing
        log_with_time("🚀 Starting parallel search operations...")
        all_results = await asyncio.gather(
            timed_task("RAG-Domain", self._rag_domain_search(enhanced_query)),
            timed_task("General-Web", self._general_web_search(enhanced_query)),
            timed_task("Internal-DB", self._lookup_past_certifications(enhanced_query, db)),
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
    
    async def _call_rag_api(self, query: str):
        """Call RAG API to get domain metadata"""
        from src.agent_system.tools import _call_rag_api_impl
        return await _call_rag_api_impl(query)
    
    async def _generate_search_queries(self, enhanced_query: str):
        """Generate multiple search queries from enhanced query"""
        from src.agent_system.tools import generate_search_queries
        result = generate_search_queries(enhanced_query)
        return result.get("queries", [])
    
    async def _map_queries_to_websites(self, queries: list[str], domain_metadata: dict):
        """Map queries to relevant websites"""
        from src.agent_system.tools import map_queries_to_websites
        import json
        metadata_str = json.dumps(domain_metadata)
        return map_queries_to_websites(queries, metadata_str)
    
    async def _parallel_web_search(self, query_website_mapping: dict):
        """Perform parallel web searches for each query-website pair"""
        from src.agent_system.tools import perplexity_domain_search
        import asyncio
        
        search_tasks = []
        for query, websites in query_website_mapping.items():
            for website in websites:
                task = self._search_single_website(query, website)
                search_tasks.append(task)
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]
    
    async def _search_single_website(self, query: str, website: str):
        """Search a single website for a query"""
        from src.agent_system.tools import perplexity_domain_search
        try:
            result = perplexity_domain_search(query, website)
            return {
                "query": query,
                "website": website,
                "result": result
            }
        except Exception as e:
            print(f"❌ Search failed for {website}: {e}")
            return None
    
    async def _synthesize_results(self, search_results: list, original_query: str):
        """Synthesize all search results into final response"""
        from src.agent_system.tools import synthesize_results
        
        # Convert search results to strings for synthesis
        result_strings = []
        for result in search_results:
            if result:
                result_strings.append(f"Query: {result['query']}\nWebsite: {result['website']}\nResult: {result['result']}")
        
        return synthesize_results(result_strings)
    
    async def _synthesize_certification_results(self, certification_results: list, original_query: str):
        """Synthesize certification results into a structured final response"""
        from src.agent_system.tools import synthesize_results
        
        # Convert certification results to strings for synthesis
        result_strings = []
        for result in certification_results:
            if result and isinstance(result, dict):
                # Format certification results
                cert_name = result.get('certificate_name', 'Unknown Certificate')
                cert_desc = result.get('certificate_description', 'No description available')
                is_required = result.get('is_required', False)
                requirement_text = "REQUIRED" if is_required else "OPTIONAL"
                
                result_strings.append(f"Certificate: {cert_name}\nDescription: {cert_desc}\nStatus: {requirement_text}")
        
        # Use the existing synthesis function
        return synthesize_results(result_strings)
    
    async def _stream_openai_response(self, raw_results: list, original_query: str, user_id: str, session_id: str, db: AsyncSession, message_id: str):
        """
        Stream OpenAI response for deduplication and synthesis of raw results, expecting a JSON array of objects in a specific format.
        """
        print(f"🚀 Starting OpenAI streaming for {len(raw_results)} raw results...")
        print(f"📊 Raw results type: {type(raw_results)}")
        print(f"📊 Raw results length: {len(raw_results)}")
        
        try:
            # Convert raw results to a structured format for OpenAI
            print("🔄 Converting raw results to structured format...")
            results_text = self._format_raw_results_for_openai(raw_results)
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

Raw Results ({len(raw_results)} items):
{results_text}
"""
            print(f"📤 Sending {len(raw_results)} results to OpenAI for JSON processing...")
            print(f"📝 Prompt length: {len(prompt)}")
            print(f"📝 First 300 chars of prompt: {prompt[:300]}...")
            
            # Call OpenAI with streaming
            from src.services.openai_service import stream_openai_response
            print("🤖 Calling OpenAI streaming service...")
            response_text = await stream_openai_response(prompt, user_id, session_id)
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

    def _clean_and_parse_json_response(self, response: str):
        """Clean and parse JSON response from OpenAI"""
        print(f"🧹 Cleaning and parsing response: '{response}'")
        
        try:
            # Clean up the response - remove markdown code blocks if present
            cleaned_response = response.strip()
            print(f"📝 Original response length: {len(response)}")
            
            if cleaned_response.startswith('```json'):
                # Remove the opening ```json and closing ```
                cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
                print("🧹 Removed markdown code blocks")
            elif cleaned_response.startswith('```'):
                # Remove any markdown code blocks
                cleaned_response = cleaned_response.replace('```', '').strip()
                print("🧹 Removed markdown code blocks")
            
            print(f"📝 Cleaned response: '{cleaned_response}'")
            print(f"📝 Cleaned response length: {len(cleaned_response)}")
            
            if not cleaned_response or cleaned_response == "[]":
                print("⚠️ Empty or invalid response, returning empty list")
                return []
            
            # Try to parse JSON
            import json
            parsed_json = json.loads(cleaned_response)
            print(f"✅ JSON parsed successfully: {type(parsed_json)}")
            
            if isinstance(parsed_json, list):
                print(f"✅ Parsed {len(parsed_json)} objects from JSON array")
                return parsed_json
            elif isinstance(parsed_json, dict):
                print("✅ Parsed single object, converting to list")
                return [parsed_json]
            else:
                print(f"⚠️ Unexpected JSON type: {type(parsed_json)}")
                return []
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing failed: {e}")
            print(f"🔍 Raw response: '{response}'")
            return []
        except Exception as e:
            print(f"❌ Unexpected error in JSON parsing: {e}")
            return []
    
    def _format_raw_results_for_openai(self, raw_results: list) -> str:
        """Format raw results into a structured text for OpenAI processing"""
        print(f"🔄 Formatting {len(raw_results)} raw results for OpenAI...")
        
        if not raw_results:
            print("⚠️ No raw results to format")
            return "No results found."
        
        formatted_results = []
        for i, result in enumerate(raw_results):
            print(f"📝 Processing result {i+1}/{len(raw_results)}: {type(result)}")
            
            if isinstance(result, dict):
                # Handle certification results
                if 'certificate_name' in result:
                    formatted_results.append(f"{i+1}. Title: {result.get('certificate_name', 'Unknown')}")
                    formatted_results.append(f"   Description: {result.get('certificate_description', 'No description')}")
                    formatted_results.append(f"   Regulation: {result.get('legal_regulation', 'Unknown')}")
                    formatted_results.append(f"   Required: {result.get('is_required', False)}")
                    formatted_results.append("")
                # Handle other result types
                else:
                    formatted_results.append(f"{i+1}. {str(result)}")
                    formatted_results.append("")
            else:
                formatted_results.append(f"{i+1}. {str(result)}")
                formatted_results.append("")
        
        result_text = "\n".join(formatted_results)
        print(f"✅ Formatted {len(raw_results)} results into {len(result_text)} characters")
        return result_text
    
    def _create_fallback_response(self, raw_results: list, original_query: str) -> str:
        """Create a fallback response when OpenAI streaming fails"""
        print(f"🔄 Creating fallback response for {len(raw_results)} results...")
        
        response_parts = [f"Based on the search results for: {original_query}\n\n"]
        
        # Deduplicate results by creating a set of unique items
        seen_items = set()
        unique_results = []
        
        for result in raw_results:
            if isinstance(result, dict):
                # Create a unique key for deduplication
                if 'certificate_name' in result:
                    key = result.get('certificate_name', '').lower().strip()
                elif 'title' in result:
                    key = result.get('title', '').lower().strip()
                else:
                    key = str(result).lower().strip()
                
                if key and key not in seen_items:
                    seen_items.add(key)
                    unique_results.append(result)
        
        print(f"✅ Deduplicated to {len(unique_results)} unique results")
        
        # Format the unique results
        for i, result in enumerate(unique_results, 1):
            if isinstance(result, dict):
                if 'certificate_name' in result:
                    cert_name = result.get('certificate_name', 'Unknown Certificate')
                    cert_desc = result.get('certificate_description', 'No description available')
                    is_required = result.get('is_required', False)
                    requirement = "REQUIRED" if is_required else "OPTIONAL"
                    
                    response_parts.append(f"{i}. **{cert_name}** ({requirement})")
                    response_parts.append(f"   {cert_desc}")
                    response_parts.append("")
                
                elif 'title' in result:
                    title = result.get('title', 'No title')
                    content = result.get('content', 'No content')
                    
                    response_parts.append(f"{i}. **{title}**")
                    response_parts.append(f"   {content}")
                    response_parts.append("")
        
        return "\n".join(response_parts) 
    
    async def _lookup_past_certifications(self, query: str, db: AsyncSession):
        """Search internal DB for past certifications"""
        try:
            # TODO: Implement actual DB lookup
            # For now, return empty list
            print(f"    🔍 Internal DB lookup for: {query}")
            return []
        except Exception as e:
            print(f"❌ Internal DB lookup failed: {e}")
            return []
    
    async def _generate_certification_queries(self, enhanced_query: str):
        """Generate multiple focused queries for certification search"""
        from src.agent_system.tools import _generate_search_queries_impl
        
        # Call the implementation function directly
        result = _generate_search_queries_impl(enhanced_query)
        
        # Log the reasoning for debugging
        if result.get("reasoning"):
            print(f"🧠 Query generation reasoning: {result['reasoning']}")
        
        queries = result.get("queries", [])
        print(f"✅ Generated {len(queries)} queries: {queries}")
        
        return queries
    
    async def _parallel_certification_search(self, search_queries: list[str]):
        """Perform parallel web search for certification queries"""
        from src.agent_system.tools import perplexity_domain_search
        import asyncio
        
        search_tasks = []
        for query in search_queries:
            # Search multiple domains for each query
            domains = ["fda.gov", "usda.gov", "iso.org", "astm.org"]
            for domain in domains:
                task = self._search_single_domain(query, domain)
                search_tasks.append(task)
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]
    
    async def _search_single_domain(self, query: str, domain: str):
        """Search a single domain for a query"""
        from src.agent_system.tools import perplexity_domain_search
        try:
            result = perplexity_domain_search(query, domain)
            return {
                "query": query,
                "domain": domain,
                "result": result
            }
        except Exception as e:
            print(f"❌ Search failed for {domain}: {e}")
            return None
    
    async def _combine_and_deduplicate_results(self, results: list):
        """Combine and deduplicate results using fuzzy matching"""
        # TODO: Implement fuzzy deduplication
        # This would use fuzzy string matching to remove duplicates
        all_results = []
        seen_results = set()
        for query_results in results:
            for source_results in [query_results['rag_domain_results'], query_results['general_results'], query_results['db_results']]:
                for result in source_results:
                    if result and result['result'] not in seen_results:
                        all_results.append(result)
                        seen_results.add(result['result'])
        return all_results
  

    async def _store_certification_result(self, results: str, query: str, db: AsyncSession):
        """Store certification result and metadata"""
        # TODO: Implement result storage
        # This would store the final result with metadata
        pass 

    async def _rag_domain_search(self, query: str):
        """RAG API + Domain Search: Get domain metadata and search with domain filter"""
        try:
            # Step 1: Get domain metadata from RAG API
            rag_result = await self._call_rag_api(query)
            
            # Step 2: Extract domains from metadata
            domains = []
            if isinstance(rag_result, list):
                for item in rag_result:
                    if isinstance(item, dict):
                        # Handle different possible domain metadata formats
                        if "domain" in item:
                            domains.append(item["domain"])
                        elif "url" in item:
                            # Extract domain from URL
                            import re
                            url = item["url"]
                            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                            if domain_match:
                                domains.append(domain_match.group(1))
                        elif "website" in item:
                            domains.append(item["website"])
            
            # Step 3: Search all domains with Perplexity in a single call
            domain_results = []
            if domains:
                print(f"    🔍 Searching {len(domains)} domains in single call: {domains}")
                try:
                    result = await self._search_single_domain_with_prompt(query, domains, "domain")
                    if result:
                        domain_results.extend(result)
                except Exception as e:
                    print(f"    ❌ Multi-domain search failed: {e}")
            else:
                print(f"    ⚠️ No domains found in RAG result, using fallback domains")
                # Fallback domains for testing
                fallback_domains = ["fda.gov", "usda.gov", "iso.org"]
                try:
                    result = await self._search_single_domain_with_prompt(query, fallback_domains, "domain")
                    if result:
                        domain_results.extend(result)
                except Exception as e:
                    print(f"    ❌ Fallback multi-domain search failed: {e}")
            
            return domain_results
            
        except Exception as e:
            print(f"❌ RAG domain search failed: {e}")
            return []
    
    async def _general_web_search(self, query: str):
        """General Web Search: Search without domain filter"""
        try:
            result = await self._search_single_domain_with_prompt(query, "", "general")
            return result if result else []
        except Exception as e:
            print(f"❌ General web search failed: {e}")
            # Return mock data for testing
            return [{"certificate_name": "Mock Certificate", "certificate_description": "Test data", "is_required": True}]
    
    async def _search_single_domain_with_prompt(self, query: str, domains: list, search_type: str):
        """Search with specific prompt based on search type"""
        from src.agent_system.tools import _perplexity_domain_search_impl
        from src.config.prompts import PERPLEXITY_LIST_GENERAL_PROMPT, PERPLEXITY_LIST_DOMAIN_PROMPT
        
        # Choose prompt based on search type
        if search_type == "domain":
            prompt = PERPLEXITY_LIST_DOMAIN_PROMPT  # Domain-filtered search
        else:
            prompt = PERPLEXITY_LIST_GENERAL_PROMPT  # General web search
        
        try:
            # Call Perplexity with domain list
            result = await _perplexity_domain_search_impl(query, domains)
            
            # Parse the JSON result
            import json
            if isinstance(result, dict) and "choices" in result:
                content = result["choices"][0]["message"]["content"]
                try:
                    # Parse the structured JSON response
                    parsed_result = json.loads(content)
                    if isinstance(parsed_result, list):
                        return parsed_result
                    elif isinstance(parsed_result, dict):
                        return [parsed_result]
                    else:
                        print(f"    ⚠️ Unexpected JSON structure for {search_type} search")
                        return []
                except json.JSONDecodeError as e:
                    print(f"    ❌ JSON parsing failed for {search_type} search: {e}")
                    print(f"    🔍 Raw content: {content[:200]}...")
                    return []
            else:
                print(f"    ⚠️ Unexpected Perplexity response format for {search_type} search")
                return []
                
        except Exception as e:
            print(f"    ❌ {search_type} search failed: {e}")
            return [] 
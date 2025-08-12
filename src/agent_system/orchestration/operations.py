"""
Operations for research and search workflows
"""
import time
import traceback
from agents import Runner
from langfuse import get_client
from openai import AsyncOpenAI
from sqlalchemy.future import select
from src.services.database_service import db_get_recent_context, db_update_memory, db_get_latest_memory
from src.config.prompts import CONTEXT_SUMMARY_PROMPT


async def web_search(query: str, use_domain: bool = False):
    """RAG API + Domain Search: Get domain metadata and search with domain filter"""
    from src.services.knowledgebase_service import kb_domain_lookup
    from src.services.perplexity_service import perplexity_search
    try:
        if use_domain:
            domains = await kb_domain_lookup(query)
        else:
            domains = None

        result = await perplexity_search(query, domains)
        return result
        
    except Exception as e:
        print(f"❌ domain web search failed: {e}")
        return {}

async def run_flashcard_agent(compliance_name: str, context: str = None, language: str = "en"):
    """Generate flashcard for a compliance using FlashcardAgent"""
    from ..agents import FlashcardAgent
    
    agent = FlashcardAgent()

    result = await Runner.run(
        agent,
        input=str({"compliance_name": compliance_name, "context": context, "language": language}),
    )

    # Convert Pydantic model to JSON string for better parsing in streaming
    final_output = result.final_output
    if hasattr(final_output, 'model_dump_json'):
        # Pydantic v2 method
        return final_output.model_dump_json()
    elif hasattr(final_output, 'json'):
        # Pydantic v1 method
        return final_output.json()
    else:
        # Fallback to regular string conversion
        return str(final_output)

async def background_run_compliance_ingestion(query: str):
    """
    Run background compliance ingestion agent
    
    Args:
        query: Search query for compliance artifacts (typically certification name)
    
    Returns:
        dict: Results with status, result, and execution time
    """
    import time
    from ..agents.background_compliance_ingestion import ComplianceIngestionAgent
    
    start_time = time.time()
    
    try:
        print(f"🔄 Starting background compliance agent for: {query[:30]}")
        
        agent = ComplianceIngestionAgent()
        langfuse = get_client()
        with langfuse.start_as_current_span(name="Background Compliance Ingestion") as span:

            result = await Runner.run(agent, input=query)
                            # Update trace once with all information
            span.update_trace(
                input=query,
                output=result.final_output,
                tags=["Background", "Update Compliance Artifact"]
            )
        
        execution_time = time.time() - start_time
        print(f"✅ Background compliance agent completed for: {query[:30]} in {execution_time:.2f}s")
        
        return {
            "status": "success",
            "query": query,
            "result": str(result.final_output),
            "execution_time": f"{execution_time:.2f}s"
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        print(f"⚠️ Background compliance agent failed for {query[:30]}: {e} (took {execution_time:.2f}s)")
        
        return {
            "status": "error",
            "query": query,
            "error": str(e),
            "error_type": type(e).__name__,
            "execution_time": f"{execution_time:.2f}s"
        }
    
async def run_compliance_discovery_agent(query: str):
    """Run compliance discovery agent"""
    from ..agents.compliance_discovery import ComplianceDiscoveryAgent
    
    agent = ComplianceDiscoveryAgent()

    result = await Runner.run(
        agent,
        input=query,
    )

    # Extract the list from the structured output
    if hasattr(result.final_output, 'response'):
        return result.final_output.response
    else:
        return result.final_output

async def background_run_context_summarization(session_id: str, latest_message_order: int):
    """
    Background conversation summarization - runs every 6 messages (3 rounds)
    
    Args:
        session_id: Session to summarize
        latest_message_order: The latest message order that triggered this summarization
    
    Returns:
        Boolean whether message saved
    """
    from src.services import AsyncSessionLocal
    
    start_time = time.time()
    
    # Create our own database session for this background task
    async with AsyncSessionLocal() as db:
        try:
            # 1) Find out what the most current memory is up until
            latest_memory = await db_get_latest_memory(db, session_id)
            start_from_order = latest_memory.up_to_message_order + 1 if latest_memory else 1
            
            # 2) Calculate how many new messages we have
            messages_to_summarize = latest_message_order - start_from_order + 1
            
            if messages_to_summarize < 6:
                return False
                
            # 3) Get context for everything in between (from last summary to current message)
            context_data = await db_get_recent_context(db, session_id, messages_to_summarize)
            messages = [{"role": "system", "content": CONTEXT_SUMMARY_PROMPT}] + context_data["messages"]
            # 4) Call OpenAI for summarization
            client = AsyncOpenAI()
            try:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.3
                )
            finally:
                await client.close()
            
            summary = response.choices[0].message.content
            
            # 5) Store the summary and update database (with transaction safety)
            try:
                # Store the summary using the latest message order passed to us
                memory_obj = await db_update_memory(db, session_id, summary, latest_message_order)
                
                # Mark the messages we just summarized as is_summarized = True
                from sqlalchemy import update
                from src.services.models import ChatSession, ChatMessage
                await db.execute(
                    update(ChatMessage)
                    .where(ChatMessage.session_id == session_id)
                    .where(ChatMessage.message_order >= start_from_order)
                    .where(ChatMessage.message_order <= latest_message_order)
                    .values(is_summarized=True)
                )
                
                # Update the chat_session to point to this latest memory
                await db.execute(
                    update(ChatSession)
                    .where(ChatSession.session_id == session_id)
                    .values(current_memory_id=memory_obj.memory_id)
                )
                
                await db.commit()
                
            except Exception as db_error:
                await db.rollback()
                raise
            
            execution_time = time.time() - start_time
            print(f"☁️ Conversation summarization completed in {execution_time:.2f}s for session: {session_id}")
            return True
            
        except Exception as e:
            execution_time = time.time() - start_time
            print(f"⚠️ Conversation summarization failed for session {session_id}: {type(e).__name__}: {e} (took {execution_time:.2f}s)")
            print(f"🔍 Full traceback: {traceback.format_exc()}")
            
            return False
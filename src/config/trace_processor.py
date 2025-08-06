"""
PostgreSQL trace processor for OpenAI Agents SDK
Stores traces temporarily and flushes to database when message_id is available
"""
from agents import TracingProcessor
from src.services.database_service import (
    db_store_trace, 
    db_store_spans, 
    parse_trace_timestamp,
)
from src.services import AsyncSessionLocal


class PostgreSQLTraceSink(TracingProcessor):
    """
    Trace processor that captures trace data and flushes to PostgreSQL 
    when assistant message_id becomes available
    """
    
    def __init__(self):
        self.pending_trace = None
        self.pending_spans = []  # Collect spans as they happen
        self.current_trace_id = None
        self.trace_start_time = None
        self.trace_end_time = None
    
    def on_trace_start(self, trace):
        """Called when a trace starts - initialize span collection"""
        self.current_trace_id = trace.trace_id
        self.pending_spans = []
        # Record actual start time
        from datetime import datetime
        self.trace_start_time = datetime.utcnow()
    
    def on_trace_end(self, trace):
        """Store trace payload temporarily - don't write to database yet"""
        self.pending_trace = trace.export()
        # Record actual end time
        from datetime import datetime
        self.trace_end_time = datetime.utcnow()
    
    def on_span_start(self, span):
        """Called when a span starts - no action needed"""
        pass
    
    def on_span_end(self, span):
        """Called when a span ends - collect span data"""
        try:
            if hasattr(span, 'export'):
                span_data = span.export()
                self.pending_spans.append(span_data)
        except Exception as e:
            print(f"⚠️ Failed to collect span data: {e}")
    
    def force_flush(self):
        """Force flush any pending data - no action needed for our delayed approach"""
        pass
    
    def shutdown(self):
        """Shutdown the processor - clear any pending data"""
        self.pending_trace = None
    
    async def flush_to_database(self, message_id: str):
        """
        Write the stored trace to PostgreSQL with the assistant message_id
        """
        if not self.pending_trace:
            return False
        
        try:
            payload = self.pending_trace
            meta = payload.get("metadata") or {}
            
            async with AsyncSessionLocal() as session:
                # Store trace using existing database service with actual timing
                trace_result = await db_store_trace(
                    db=session,
                    trace_id=payload["id"],
                    workflow_name=payload.get("workflow_name", "unknown"),
                    started_at=self.trace_start_time,
                    ended_at=self.trace_end_time,
                    status=payload.get("status"),
                    trace_metadata=meta,
                    usage_json=payload.get("usage", {}),
                    raw_json=payload,
                    message_id=message_id
                )
                
                if trace_result:
                    # Use collected spans instead of payload spans (which are empty due to timing)
                    spans_data = []
                    for span_data in self.pending_spans:
                        try:
                            # Extract name from span_data.name if available, otherwise use span type
                            span_name = span_data.get("span_data", {}).get("name")
                            if not span_name or span_name == "none":
                                span_name = span_data["span_data"]["type"]  # Use type as fallback
                                
                            spans_data.append({
                                "span_id": span_data["id"],
                                "trace_id": span_data["trace_id"],
                                "parent_id": span_data.get("parent_id"),
                                "name": span_name,
                                "span_type": span_data["span_data"]["type"],
                                "started_at": parse_trace_timestamp(span_data.get("started_at")),
                                "ended_at": parse_trace_timestamp(span_data.get("ended_at")),
                                "data": span_data["span_data"]
                            })
                        except KeyError as e:
                            print(f"⚠️ Span missing key {e}: {span_data}")
                    
                    # Store spans using existing database service
                    await db_store_spans(session, spans_data)
                    
                    self.pending_trace = None  # Clear after successful write
                    self.pending_spans = []   # Clear collected spans
                    return True
                else:
                    return False
                    
        except Exception as e:
            print(f"⚠️ Error flushing trace to PostgreSQL: {e}")
            return False


# Global instance to be used across the application
postgres_sink = PostgreSQLTraceSink()


def setup_postgresql_trace_processor():
    """
    Register PostgreSQL trace processor alongside existing Langfuse tracing
    """
    try:
        from agents import add_trace_processor
        
        add_trace_processor(postgres_sink)
        
        return True
        
    except ImportError:
        return False
    except Exception:
        return False
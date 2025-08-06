"""
Langfuse configuration for BlueJay agent tracing with enhanced features
"""
import os
import logfire
import nest_asyncio

# Global flag to prevent multiple configurations
_langfuse_configured = False

def setup_langfuse_tracing():
    """
    Setup Langfuse tracing using official Langfuse approach
    """
    global _langfuse_configured
    
    # Check if already configured
    if _langfuse_configured:
        print("⚠️  Langfuse tracing already configured, skipping")
        return True
    
    try:
        # Check credentials
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY") 
        host = os.getenv("LANGFUSE_HOST")
        
        if not all([public_key, secret_key, host]):
            print("⚠️  Langfuse credentials not found in environment. Tracing disabled.")
            return False
        
        print(f"🔧 Setting up Langfuse tracing for: {host}")
        
        # Apply nest_asyncio for compatibility
        nest_asyncio.apply()
        
        # Configure logfire instrumentation (suppress console output)
        import logging
        logging.getLogger('logfire').setLevel(logging.WARNING)
        logging.getLogger('opentelemetry').setLevel(logging.WARNING)
        
        logfire.configure(
            service_name='bluejay_agent_service',
            send_to_logfire=False,
            console=False,  # Disable console output
        )
        logfire.instrument_openai_agents()
        
        # Verify authentication
        from langfuse import get_client
        langfuse = get_client()
        
        if langfuse.auth_check():
            print("✅ Langfuse tracing configured successfully!")
            print(f"📊 Dashboard: {host}")
            
            _langfuse_configured = True
            return True
        else:
            print("❌ Langfuse authentication failed")
            return False
        
    except ImportError as e:
        print(f"⚠️  Missing dependencies: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Failed to setup Langfuse tracing: {e}")
        return False
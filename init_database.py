#!/usr/bin/env python3
"""
Database initialization script to create all tables
"""
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from src.database.models import Base
from src.database.services import db_service

async def init_database():
    """Initialize database tables"""
    print("Initializing database tables...")
    
    try:
        # Get the engine from the database service
        engine = db_service.engine
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✓ All database tables created successfully!")
        
        # Test the connection by querying the tables
        async for session in db_service.get_session():
            from sqlalchemy import text
            result = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = result.fetchall()
            print(f"✓ Found {len(tables)} tables in database:")
            for table in tables:
                print(f"  - {table[0]}")
            break
            
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False
    
    return True

async def test_table_access():
    """Test accessing the created tables"""
    print("\nTesting table access...")
    
    try:
        async for session in db_service.get_session():
            from src.database.models import ChatSession, ChatMessage, ResearchRequest, ConversationMemory
            
            # Test each table
            tables_to_test = [
                ("chat_sessions", ChatSession),
                ("chat_messages", ChatMessage), 
                ("research_requests", ResearchRequest),
                ("conversation_memory", ConversationMemory)
            ]
            
            for table_name, model in tables_to_test:
                try:
                    from sqlalchemy.future import select
                    result = await session.execute(select(model).limit(1))
                    count = len(result.scalars().all())
                    print(f"✓ {table_name}: {count} records")
                except Exception as e:
                    print(f"✗ {table_name}: {e}")
            
            break
            
    except Exception as e:
        print(f"✗ Table access test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    load_dotenv()
    
    print("=== Database Initialization ===\n")
    
    # Initialize database
    success = asyncio.run(init_database())
    
    if success:
        # Test table access
        asyncio.run(test_table_access())
        print("\n🎉 Database initialization completed successfully!")
    else:
        print("\n❌ Database initialization failed!")
        print("\nTroubleshooting tips:")
        print("1. Check database permissions")
        print("2. Verify database user has CREATE TABLE privileges")
        print("3. Check if tables already exist")
        print("4. Verify database connection") 
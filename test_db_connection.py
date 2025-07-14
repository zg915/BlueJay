#!/usr/bin/env python3
"""
Test script to verify database connection with new setup
"""
import asyncio
import os
from dotenv import load_dotenv
from src.database.services import db_service
from src.database.models import ChatSession

async def test_database_connection():
    """Test the database connection"""
    print("Testing database connection...")
    
    try:
        # Test getting a session
        async for session in db_service.get_session():
            print("✓ Database session created successfully")
            
            # Test a simple query
            from sqlalchemy.future import select
            result = await session.execute(select(ChatSession).limit(1))
            sessions = result.scalars().all()
            print(f"✓ Database query successful - found {len(sessions)} sessions")
            
            break
            
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False
    
    print("✓ All database tests passed!")
    return True

async def test_environment_variables():
    """Test that environment variables are loaded correctly"""
    print("\nChecking environment variables...")
    
    required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✓ {var}: {value}")
        else:
            print(f"✗ {var}: Not set")
    
    # Test the connection string
    from src.database import get_database_url
    connection_string = get_database_url()
    print(f"✓ Connection string: {connection_string}")

if __name__ == "__main__":
    load_dotenv()
    
    print("=== Database Connection Test ===\n")
    
    # Test environment variables
    asyncio.run(test_environment_variables())
    
    # Test database connection
    success = asyncio.run(test_database_connection())
    
    if success:
        print("\n🎉 Database connection test completed successfully!")
    else:
        print("\n❌ Database connection test failed!")
        print("\nTroubleshooting tips:")
        print("1. Check your .env file has all required variables")
        print("2. Verify database server is running")
        print("3. Check network connectivity to database")
        print("4. Verify database credentials") 
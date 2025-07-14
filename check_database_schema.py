#!/usr/bin/env python3
"""
Check database schema to see what tables and columns exist
"""
import asyncio
import os
from dotenv import load_dotenv
from src.database.services import db_service

async def check_database_schema():
    """Check what tables and columns exist in the database"""
    print("=== Database Schema Check ===\n")
    
    try:
        async for session in db_service.get_session():
            from sqlalchemy import text
            
            # Check what tables exist
            print("📋 Existing Tables:")
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = result.fetchall()
            
            if not tables:
                print("❌ No tables found in database!")
                return
            
            for table in tables:
                table_name = table[0]
                print(f"\n📊 Table: {table_name}")
                
                # Check columns for this table
                result = await session.execute(text(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """))
                columns = result.fetchall()
                
                print(f"   Columns:")
                for col in columns:
                    col_name, data_type, is_nullable, default_val = col
                    nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
                    default = f" DEFAULT {default_val}" if default_val else ""
                    print(f"     - {col_name}: {data_type} {nullable}{default}")
            
            break
            
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return False
    
    return True

async def check_expected_vs_actual():
    """Compare expected schema with actual schema"""
    print("\n=== Expected vs Actual Schema ===\n")
    
    expected_tables = {
        "chat_sessions": ["id", "user_id", "created_at"],
        "chat_messages": ["id", "session_id", "user_id", "content", "timestamp"],
        "research_requests": ["id", "session_id", "user_id", "question", "created_at"],
        "conversation_memory": ["memory_id", "session_id", "summary", "up_to_message_order", "created_at", "summarization_strategy"]
    }
    
    try:
        async for session in db_service.get_session():
            from sqlalchemy import text
            
            for table_name, expected_columns in expected_tables.items():
                print(f"📋 {table_name}:")
                
                # Check if table exists
                result = await session.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table_name}'
                    )
                """))
                table_exists = result.scalar()
                
                if not table_exists:
                    print(f"   ❌ Table does not exist")
                    continue
                
                # Get actual columns
                result = await session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """))
                actual_columns = [row[0] for row in result.fetchall()]
                
                print(f"   ✅ Table exists")
                print(f"   Expected columns: {expected_columns}")
                print(f"   Actual columns: {actual_columns}")
                
                # Check for missing columns
                missing = set(expected_columns) - set(actual_columns)
                extra = set(actual_columns) - set(expected_columns)
                
                if missing:
                    print(f"   ❌ Missing columns: {list(missing)}")
                if extra:
                    print(f"   ⚠️  Extra columns: {list(extra)}")
                if not missing and not extra:
                    print(f"   ✅ Schema matches expected")
                
                print()
            
            break
            
    except Exception as e:
        print(f"❌ Error comparing schemas: {e}")
        return False
    
    return True

if __name__ == "__main__":
    load_dotenv()
    
    print("Checking database schema...\n")
    
    # Check current schema
    asyncio.run(check_database_schema())
    
    # Compare with expected schema
    asyncio.run(check_expected_vs_actual())
    
    print("\n💡 Recommendations:")
    print("1. If tables don't exist, run: python init_database.py")
    print("2. If tables exist but have wrong schema, drop them and recreate:")
    print("   DROP TABLE IF EXISTS chat_sessions, chat_messages, research_requests, conversation_memory CASCADE;")
    print("   Then run: python init_database.py")
    print("3. If you want to keep existing data, you'll need to create a migration script") 
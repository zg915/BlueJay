"""
OpenAI service integration for demo4
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI
import os


class OpenAIService:
    """Service class for OpenAI API interactions"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  # Use a cost-effective model
    
    async def stream_openai_response(self, prompt: str, user_id: str, session_id: str) -> str:
        """
        Stream OpenAI response for processing raw results
        """
        print(f"🚀 Starting OpenAI streaming for user {user_id}, session {session_id}")
        
        try:
            # Create the streaming response
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that processes and synthesizes search results. Provide clear, well-organized responses."},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Collect the full response
            full_response = ""
            print("📡 Streaming response from OpenAI...")
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    # You could yield content here for real-time streaming
                    print(f"📝 Received chunk: {len(content)} characters")
            
            print(f"✅ Streaming completed. Total response length: {len(full_response)} characters")
            return full_response
            
        except Exception as e:
            print(f"❌ Error in OpenAI streaming: {e}")
            raise
    
    async def process_raw_results(self, raw_results: List[Dict], original_query: str) -> str:
        """
        Process raw results through OpenAI for deduplication and synthesis
        """
        print(f"🔍 Processing {len(raw_results)} raw results through OpenAI...")
        
        # Format raw results for processing
        results_text = self._format_results_for_processing(raw_results)
        
        prompt = f"""
        Original Query: {original_query}
        
        Raw Results ({len(raw_results)} items):
        {results_text}
        
        Please:
        1. Deduplicate the results (remove exact and similar duplicates)
        2. Organize them logically
        3. Provide a comprehensive, well-structured response
        4. Include all relevant information from the raw results
        
        Format the response in a clear, organized manner suitable for the user's query.
        """
        
        return await self.stream_openai_response(prompt, "user", "session")
    
    def _format_results_for_processing(self, raw_results: List[Dict]) -> str:
        """Format raw results into a structured text for OpenAI processing"""
        formatted_results = []
        
        for i, result in enumerate(raw_results, 1):
            if isinstance(result, dict):
                # Handle certification results
                if 'certificate_name' in result:
                    cert_name = result.get('certificate_name', 'Unknown')
                    cert_desc = result.get('certificate_description', 'No description')
                    is_required = result.get('is_required', False)
                    requirement = "REQUIRED" if is_required else "OPTIONAL"
                    
                    formatted_results.append(f"{i}. Certificate: {cert_name}")
                    formatted_results.append(f"   Description: {cert_desc}")
                    formatted_results.append(f"   Status: {requirement}")
                    formatted_results.append("")
                
                # Handle general research results
                elif 'title' in result or 'content' in result:
                    title = result.get('title', 'No title')
                    content = result.get('content', 'No content')
                    source = result.get('source', 'Unknown source')
                    
                    formatted_results.append(f"{i}. Title: {title}")
                    formatted_results.append(f"   Content: {content}")
                    formatted_results.append(f"   Source: {source}")
                    formatted_results.append("")
                
                # Handle other result types
                else:
                    formatted_results.append(f"{i}. {str(result)}")
                    formatted_results.append("")
        
        return "\n".join(formatted_results)


# Global instance for easy access
openai_service = OpenAIService()


async def stream_openai_response(prompt: str, user_id: str, session_id: str) -> str:
    """Convenience function to stream OpenAI response"""
    return await openai_service.stream_openai_response(prompt, user_id, session_id) 
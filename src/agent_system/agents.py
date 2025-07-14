from agents import Agent, handoff, function_tool
from src.agent_system.tools import (
    get_recent_context,
    call_rag_api,
    generate_search_queries,
    map_queries_to_websites,
    perplexity_domain_search,
    create_parallel_queries,
    run_parallel_queries,
    synthesize_results
)
from src.config.prompts import (
    TRIAGE_AGENT_PROMPT,
    LIST_GENERATION_AGENT_PROMPT,
    RESEARCH_AGENT_PROMPT,
    DIRECT_RESPONSE_AGENT_PROMPT
)

# TriageAgent: Classifies question type with handoffs
class TriageAgent(Agent):
    def __init__(self, certification_agent=None, research_agent=None, direct_agent=None):
        handoffs_list = []
        if certification_agent:
            handoffs_list.append(handoff(certification_agent, tool_name_override="transfer_to_certification_agent"))
        if research_agent:
            handoffs_list.append(handoff(research_agent, tool_name_override="transfer_to_research_agent"))
        if direct_agent:
            handoffs_list.append(handoff(direct_agent, tool_name_override="transfer_to_direct_agent"))
        
        super().__init__(
            name="TriageAgent",
            instructions=TRIAGE_AGENT_PROMPT,
            tools=[get_recent_context],
            handoffs=handoffs_list
        )

# ListGenerationAgent: Handles list requests
class ListGenerationAgent(Agent):
    def __init__(self):
        super().__init__(
            name="ListGenerationAgent",
            instructions=LIST_GENERATION_AGENT_PROMPT,
            tools=[get_recent_context, call_rag_api, generate_search_queries, map_queries_to_websites, perplexity_domain_search, create_parallel_queries, run_parallel_queries, synthesize_results],
        )

# ResearchAgent: Handles research/information-seeking requests
class ResearchAgent(Agent):
    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            instructions=RESEARCH_AGENT_PROMPT,
            tools=[get_recent_context, call_rag_api, generate_search_queries, map_queries_to_websites, perplexity_domain_search, create_parallel_queries, run_parallel_queries, synthesize_results],
        )

# DirectResponseAgent: Handles simple questions
class DirectResponseAgent(Agent):
    def __init__(self):
        super().__init__(
            name="DirectResponseAgent",
            instructions=DIRECT_RESPONSE_AGENT_PROMPT,
            tools=[get_recent_context, synthesize_results],
        ) 
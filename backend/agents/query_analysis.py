from backend.agents.state import AgentState
from backend.config import settings
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.openai_api_key)

QUERY_ANALYSIS_PROMPT = """You are a query analysis expert. Analyze the user's query and provide structured information.

{context}

User Query: {query}

Analyze and provide:
1. Query Type: Classify as "factual", "analytical", or "comparative"
   - factual: Simple fact-based questions (What is X? Who is Y?)
   - analytical: Requires analysis or explanation (How does X work? Why does Y happen?)
   - comparative: Comparing multiple things (X vs Y, differences between A and B)

2. Search Strategy: Determine "documents" or "hybrid"
   - documents: USE THIS FOR ALMOST ALL QUERIES. If the query asks about any topic, concept, definition, process, or entity, assume it might be in the knowledge base.
   - hybrid: Use ONLY if the user EXPLICITLY asks for both internal documentation AND external/current web information (e.g. "Compare our internal process with industry standards").
   - web: Use ONLY for greetings, purely conversational inputs (like "how are you"), or simple thank yous. DO NOT use for informational queries even if they seem general.

3. Optimized Query: Reformulate the query for better retrieval
   - Expand acronyms and add context
   - If this is a follow-up question, incorporate context from previous conversation
   - Resolve pronouns (it, that, this) using conversation context

4. Search Parameters:
   - top_k: Number of chunks to retrieve (5-10)
   - alpha: Hybrid search weight (0.5-0.9, higher for semantic queries)

Respond in this exact JSON format:
{{
    "query_type": "factual|analytical|comparative",
    "search_strategy": "documents|web|hybrid",
    "optimized_query": "reformulated query here",
    "search_params": {{"top_k": 5, "alpha": 0.7}}
}}
"""

def query_analysis_agent(state: AgentState) -> AgentState:
    """
    Query Analysis Agent - Analyzes query intent and optimizes retrieval strategy.
    
    Responsibilities:
    - Classify query type
    - Determine search strategy
    - Optimize query for retrieval (with conversation context)
    - Set search parameters
    
    Args:
        state: Current agent state
    
    Returns:
        AgentState: Updated state with query analysis
    """
    logger.info(f"Query Analysis: Analyzing query: {state['query']}")
    
    # Add to trace
    state["agent_trace"].append("query_analysis")
    
    # Get conversation context from state
    chat_history = state.get("chat_history", [])
    context_str = ""
    
    if chat_history:
        # Format last 25 turns for context (50 messages)
        recent_history = chat_history[-50:]
        context_parts = []
        for msg in recent_history:
            role = "User" if msg["type"] == "user" else "Assistant"
            content = msg["content"]
            # Truncate long content
            if len(content) > 500:
                content = content[:500] + "..."
            context_parts.append(f"{role}: {content}")
        
        context_str = "Previous Conversation:\n" + "\n".join(context_parts)
    else:
        context_str = "No previous conversation context."
    
    try:
        # Call LLM for query analysis
        response = openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a query analysis expert. Always respond with valid JSON."},
                {"role": "user", "content": QUERY_ANALYSIS_PROMPT.format(
                    query=state["query"],
                    context=context_str
                )}
            ],
            temperature=0.3,  # Low temperature for consistent analysis
            response_format={"type": "json_object"}
        )
        
        # Parse response
        import json
        analysis = json.loads(response.choices[0].message.content)
        
        # Update state
        state["query_type"] = analysis.get("query_type", "factual")
        state["search_strategy"] = analysis.get("search_strategy", "documents")
        state["optimized_query"] = analysis.get("optimized_query", state["query"])
        state["search_params"] = analysis.get("search_params", {"top_k": 5, "alpha": 0.7})
        
        logger.info(f"Query Analysis: Type={state['query_type']}, Strategy={state['search_strategy']}")
        logger.info(f"Query Analysis: Optimized query: {state['optimized_query']}")
        
    except Exception as e:
        logger.error(f"Query Analysis: Error during analysis: {e}")
        # Fallback to defaults
        state["query_type"] = "factual"
        state["search_strategy"] = "documents"
        state["optimized_query"] = state["query"]
        state["search_params"] = {"top_k": 5, "alpha": 0.7}
    
    return state

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from backend.agents.state import AgentState
from backend.agents.orchestrator import orchestrator_agent
from backend.agents.query_analysis import query_analysis_agent
from backend.agents.retrieval import retrieval_agent
from backend.agents.reranking import reranking_agent
from backend.agents.generation import generation_agent
from backend.agents.citation import citation_agent
import logging
import os

logger = logging.getLogger(__name__)

# Create the workflow graph
workflow = StateGraph(AgentState)

# Add nodes (agents)
workflow.add_node("orchestrator", orchestrator_agent)
workflow.add_node("query_analysis", query_analysis_agent)
workflow.add_node("retrieval", retrieval_agent)
workflow.add_node("reranking", reranking_agent)
workflow.add_node("generation", generation_agent)
workflow.add_node("citation", citation_agent)

# Define the workflow edges
workflow.set_entry_point("orchestrator")
workflow.add_edge("orchestrator", "query_analysis")
workflow.add_edge("query_analysis", "retrieval")
workflow.add_edge("retrieval", "reranking")
workflow.add_edge("reranking", "generation")
workflow.add_edge("generation", "citation")
workflow.add_edge("citation", END)

# Create SQLite checkpointer for persistent conversation storage
import sqlite3

db_path = "conversations.db"

# Initialize connection and create SqliteSaver
conn = sqlite3.connect(db_path, check_same_thread=False)
memory = SqliteSaver(conn)

# Compile the workflow with persistent memory
app = workflow.compile(checkpointer=memory)

logger.info(f"LangGraph workflow compiled with SQLite persistence: {db_path}")


async def run_query(query: str, conversation_id: str = None) -> dict:
    """
    Run a query through the multi-agent workflow with LangGraph memory.
    
    Args:
        query: User's question
        conversation_id: Optional conversation ID for follow-ups (thread_id)
    
    Returns:
        dict: Final response with answer and citations
    """
    from backend.agents.state import create_initial_state
    import uuid
    
    logger.info(f"Running query: {query}")
    
    # Use conversation_id as thread_id for LangGraph memory
    thread_id = conversation_id or str(uuid.uuid4())
    
    # Create initial state
    initial_state = create_initial_state(query, thread_id)
    
    # Configure with thread_id for conversation tracking
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    # Run the workflow with memory (ASYNC)
    final_state = await app.ainvoke(initial_state, config)
    
    # Format response
    response = {
        "answer": final_state.get("answer", ""),
        "citations": [
            {
                "document_name": c.document_name,
                "page_number": c.page_number,
                "chunk_text": c.chunk_text,
                "relevance_score": c.relevance_score,
                "url": getattr(c, 'url', None)
            }
            for c in final_state.get("citations", [])
        ],
        "conversation_id": thread_id,
        "used_web_search": final_state.get("used_web_search", False),
        "query_type": final_state.get("query_type", ""),
        "agent_trace": final_state.get("agent_trace", [])
    }
    
    logger.info(f"Query completed. Agent trace: {response['agent_trace']}")
    logger.info(f"Conversation persisted with thread_id: {thread_id}")
    
    # Save messages to database for fast retrieval (O(1) instead of O(N) state reconstruction)
    try:
        import backend.database as database
        
        # Save user query
        database.save_message(
            conversation_id=thread_id,
            role="user",
            content=query
        )
        
        # Save assistant answer
        database.save_message(
            conversation_id=thread_id,
            role="assistant",
            content=response["answer"],
            citations=response["citations"]
        )
    except Exception as e:
        logger.error(f"Failed to save messages to DB: {e}")
    
    return response


def get_conversation_history(conversation_id: str) -> list:
    """
    Get conversation history using LangGraph's memory.
    
    Args:
        conversation_id: Thread ID for the conversation
    
    Returns:
        List of messages in the format: [{"type": "user"/"assistant", "content": str, "citations": []}]
    """
    config = {
        "configurable": {
            "thread_id": conversation_id
        }
    }
    
    # Get state history from memory
    messages = []
    query_to_state = {}  # Map queries to their LAST (most complete) state
    
    try:
        # Get all state snapshots for this thread
        state_history = list(app.get_state_history(config))
        
        logger.info(f"Retrieved {len(state_history)} state snapshots for conversation {conversation_id}")
        
        # Build a map of queries to their final states
        # State history is ordered from newest to oldest
        for state_snapshot in state_history:
            state = state_snapshot.values
            
            # Skip if this is the initial state (no answer yet)
            if not state.get("answer"):
                continue
            
            query = state.get("query", "")
            if not query:
                continue
            
            # Keep the FIRST occurrence we see (which is the NEWEST/LAST in chronological order)
            # because state_history is ordered newest to oldest
            if query not in query_to_state:
                query_to_state[query] = state
        
        # Now extract messages in chronological order
        # We need to reverse to get oldest first
        queries_in_order = list(query_to_state.keys())
        queries_in_order.reverse()
        
        for query in queries_in_order:
            state = query_to_state[query]
            
            # Add user message (query)
            messages.append({
                "type": "user",
                "content": query
            })
            
            # Add assistant message (answer with citations)
            citations = []
            if state.get("citations"):
                try:
                    logger.info(f"Processing {len(state['citations'])} citations for query: {query[:50]}...")
                    citations = [
                        {
                            "document_name": c.document_name if hasattr(c, 'document_name') else c.get('document_name', ''),
                            "page_number": c.page_number if hasattr(c, 'page_number') else c.get('page_number', 0),
                            "chunk_text": c.chunk_text if hasattr(c, 'chunk_text') else c.get('chunk_text', ''),
                            "relevance_score": c.relevance_score if hasattr(c, 'relevance_score') else c.get('relevance_score', 0.0),
                        }
                        for c in state["citations"]
                    ]
                    logger.info(f"Successfully processed {len(citations)} citations")
                except Exception as citation_error:
                    logger.warning(f"Error processing citations: {citation_error}")
                    citations = []
            else:
                logger.warning(f"No citations found in state for query: {query[:50]}...")
            
            messages.append({
                "type": "assistant",
                "content": state["answer"],
                "citations": citations
            })
        
        logger.info(f"Extracted {len(messages)} messages from conversation {conversation_id}")
        
    except Exception as e:
        logger.error(f"Error retrieving conversation history: {e}")
        logger.exception(e)
    
    return messages


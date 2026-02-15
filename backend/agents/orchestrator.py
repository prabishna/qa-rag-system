from backend.agents.state import AgentState
from backend.config import settings
import logging
import uuid

logger = logging.getLogger(__name__)

def orchestrator_agent(state: AgentState) -> AgentState:
    """
    Orchestrator Agent - Coordinates the multi-agent workflow.
    
    Responsibilities:
    - Initialize conversation ID if not present
    - Set up logging and tracing
    - Validate input
    - Prepare state for downstream agents
    
    Args:
        state: Current agent state
    
    Returns:
        AgentState: Updated state with initialization
    """
    logger.info(f"Orchestrator: Starting workflow for query: {state['query'][:50]}...")
    
    # Ensure conversation ID exists
    if not state.get("conversation_id"):
        state["conversation_id"] = str(uuid.uuid4())
        logger.info(f"Orchestrator: Created conversation ID: {state['conversation_id']}")
    
    # Add orchestrator to trace
    state["agent_trace"].append("orchestrator")
    
    # Initialize empty fields if not present
    if not state.get("search_params"):
        state["search_params"] = {}
    
    if not state.get("retrieved_chunks"):
        state["retrieved_chunks"] = []
    
    if not state.get("web_results"):
        state["web_results"] = []
    
    if not state.get("reranked_chunks"):
        state["reranked_chunks"] = []
    
    if not state.get("citations"):
        state["citations"] = []
    
    # Validate query
    if not state["query"] or not state["query"].strip():
        logger.error("Orchestrator: Empty query received")
        state["answer"] = "Error: Empty query provided"
        return state
    
    logger.info(f"Orchestrator: Initialization complete. Routing to query analysis.")
    
    return state

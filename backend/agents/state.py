from typing import TypedDict, List, Optional, Annotated
from backend.models.schemas import Citation
import operator

class AgentState(TypedDict):
    """
    State shared across all agents in the workflow.
    Uses TypedDict for LangGraph compatibility.
    """
    # Input
    query: str
    conversation_id: str
    
    # Query Analysis
    query_type: str                         # "factual" | "analytical" | "comparative"
    search_strategy: str                    # "documents" | "web" | "hybrid"
    optimized_query: str                    # Reformulated query for better retrieval
    search_params: dict                     # {top_k: int, alpha: float}
    
    # Retrieval
    retrieved_chunks: List[dict]            # Chunks from vector DB
    web_results: List[dict]                 # Results from web search
    
    # Re-ranking
    reranked_chunks: List[dict]             # Re-scored and filtered chunks
    
    # Generation
    answer: str                             # Generated answer
    reasoning: str                          # Reasoning behind the answer
    
    # Citation
    citations: List[Citation]               # Source citations
    
    # Metadata
    used_web_search: bool                   # Flag if web search was used
    agent_trace: Annotated[List[str], operator.add]  # Track agent execution order
    
    # Context
    chat_history: List[dict]                # Conversation history for context


# Helper function to create initial state
def create_initial_state(query: str, conversation_id: str = None) -> AgentState:
    """
    Create initial agent state from user query.
    
    Args:
        query: User's question
        conversation_id: Optional conversation ID for follow-ups
    
    Returns:
        AgentState: Initialized state
    """
    import uuid
    import backend.database as database
    
    # Fetch conversation history if ID exists
    chat_history = []
    if conversation_id:
        try:
            chat_history = database.get_conversation_messages(conversation_id)
        except Exception:
            chat_history = []
    
    return AgentState(
        query=query,
        conversation_id=conversation_id or str(uuid.uuid4()),
        query_type="",
        search_strategy="",
        optimized_query="",
        search_params={},
        retrieved_chunks=[],
        web_results=[],
        reranked_chunks=[],
        answer="",
        reasoning="",
        citations=[],
        used_web_search=False,
        agent_trace=[],
        chat_history=chat_history
    )

from backend.agents.state import AgentState
from backend.utils.mcp_client import VectorDBClient, WebSearchClient
import logging

logger = logging.getLogger(__name__)

async def retrieval_agent(state: AgentState) -> AgentState:
    """
    Retrieval Agent - Fetches relevant information via MCP servers.
    
    Responsibilities:
    - Search vector database using Vector DB MCP server
    - Fallback to web search using Web Search MCP server
    - Preserve metadata (source, page, scores)
    
    Args:
        state: Current agent state
    
    Returns:
        AgentState: Updated state with retrieved chunks
    """
    logger.info(f"Retrieval: Starting retrieval with strategy: {state['search_strategy']}")
    
    # Add to trace
    state["agent_trace"].append("retrieval")
    
    # Get search parameters
    top_k = state["search_params"].get("top_k", 5)
    alpha = state["search_params"].get("alpha", 0.7)
    query = state["optimized_query"] or state["query"]
    
    retrieved_chunks = []
    
    # Try document search first (if strategy allows)
    if state["search_strategy"] in ["documents", "hybrid"]:
        try:
            logger.info(f"Retrieval: Searching Milvus via MCP with top_k={top_k}, alpha={alpha}")
            
            # Use MCP Tool for better separation of concerns (ASYNC via SSE)
            result = await VectorDBClient.search_documents_async(
                query=query,
                top_k=top_k * 2,
                alpha=alpha
            )
            
            if result.get("status") == "success":
                chunks = result.get("chunks", [])
                
                # Format results
                for chunk in chunks:
                    retrieved_chunks.append({
                        "chunk_id": chunk.get("chunk_id"),
                        "chunk_text": chunk.get("chunk_text"),
                        "document_name": chunk.get("document_name"),
                        "page_number": chunk.get("page_number"),
                        "vector_score": chunk.get("vector_score"),
                        "keyword_score": chunk.get("keyword_score"),
                        "combined_score": chunk.get("combined_score"),
                        "source_type": "document"
                    })
                
                logger.info(f"Retrieval: Found {len(retrieved_chunks)} chunks from Vector DB MCP")
            else:
                logger.error(f"Retrieval: Vector DB MCP returned error: {result.get('message')}")
                
        except Exception as e:
            logger.error(f"Vector DB retrieval failed: {e}", exc_info=True)
    
    # Web search if needed
    if state["search_strategy"] in ["web", "hybrid"] or len(retrieved_chunks) < 3:
        try:
            logger.info(f"Retrieval: Calling Web Search MCP")
            state["used_web_search"] = True
            
            # Call Web Search MCP server (ASYNC via SSE)
            result = await WebSearchClient.web_search_async(
                query=query,
                max_results=5
            )
            
            if result.get("status") == "success":
                # Add web results to chunks
                for idx, web_result in enumerate(result.get("results", [])):
                    retrieved_chunks.append({
                        "chunk_id": f"web_{idx}",
                        "chunk_text": web_result["snippet"],
                        "document_name": web_result["title"],
                        "page_number": None,
                        "vector_score": 0.0,
                        "keyword_score": 0.0,
                        "combined_score": 0.5,  # Default score for web results
                        "source_type": "web",
                        "url": web_result["url"]
                    })
                
                logger.info(f"Retrieval: Found {len(result.get('results', []))} results from Web Search MCP")
            else:
                logger.error(f"Retrieval: Web Search MCP returned error: {result.get('message')}")
            
        except Exception as e:
            logger.error(f"Retrieval: Error calling Web Search MCP: {e}")
    
    # Update state
    state["retrieved_chunks"] = retrieved_chunks
    
    logger.info(f"Retrieval: Total chunks retrieved: {len(retrieved_chunks)}")
    
    return state


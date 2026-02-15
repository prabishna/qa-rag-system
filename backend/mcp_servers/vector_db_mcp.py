from fastmcp import FastMCP
from backend.utils.milvus_client import milvus_client
from backend.config import settings
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Vector Database Server")

# OpenAI client for creating query embeddings
openai_client = OpenAI(api_key=settings.openai_api_key)

@mcp.tool()
def search_documents(query: str, top_k: int = 5, alpha: float = 0.7) -> dict:
    """
    Search for relevant document chunks using hybrid search (vector + keyword).
    
    Args:
        query: The search query
        top_k: Number of results to return (default: 5)
        alpha: Weight for vector search (default: 0.7 = 70% vector, 30% keyword)
    
    Returns:
        dict: Search results with chunks and relevance scores
    """
    try:
        # Create embedding for the query
        response = openai_client.embeddings.create(
            model=settings.embedding_model,
            input=query
        )
        query_embedding = response.data[0].embedding
        
        # Hybrid search (vector + keyword)
        results = milvus_client.hybrid_search(query_embedding, query, top_k, alpha)
        
        # Format results
        chunks = []
        for result in results:
            hit = result["hit"]
            chunks.append({
                "chunk_id": hit.id,
                "document_name": hit.entity.get("document_name"),
                "chunk_text": hit.entity.get("chunk_text"),
                "page_number": hit.entity.get("page_number"),
                "vector_score": result["vector_score"],
                "keyword_score": result["keyword_score"],
                "combined_score": result["combined_score"]
            })
        
        return {
            "status": "success",
            "query": query,
            "search_type": "hybrid",
            "num_results": len(chunks),
            "chunks": chunks
        }
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
def delete_documents(expr: str) -> dict:
    """
    Delete documents from the vector database.
    
    Args:
        expr: Boolean expression to filter documents to delete (e.g. 'document_id == "123"')
    
    Returns:
        dict: Status of deletion
    """
    try:
        milvus_client.delete_documents(expr)
        return {
            "status": "success",
            "message": f"Documents matching '{expr}' deleted successfully"
        }
    except Exception as e:
        logger.error(f"Deletion failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    mcp.run(transport='sse', port=8001, host='0.0.0.0')
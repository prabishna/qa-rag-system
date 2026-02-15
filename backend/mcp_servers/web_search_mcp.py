from fastmcp import FastMCP
from duckduckgo_search import DDGS
import logging

logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Web Search Server")

@mcp.tool()
def web_search(query: str, max_results: int = 5) -> dict:
    """
    Search the web using DuckDuckGo.
    
    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        dict: Search results with titles, snippets, and URLs
    """
    try:
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=max_results))
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result.get("title", ""),
                "snippet": result.get("body", ""),
                "url": result.get("href", "")
            })
        
        return {
            "status": "success",
            "query": query,
            "num_results": len(formatted_results),
            "results": formatted_results
        }
    
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    mcp.run(transport='sse', port=8002, host='0.0.0.0')
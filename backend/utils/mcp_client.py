"""
MCP Client for connecting to MCP servers via SSE (HTTP).
Provides a unified interface for calling MCP server tools.
"""

from mcp import ClientSession
from mcp.client.sse import sse_client
from typing import Any, Dict, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Client for interacting with MCP servers via SSE.
    """
    
    def __init__(self, server_name: str, server_url: str):
        """
        Initialize MCP client for a specific server.
        
        Args:
            server_name: Name of the MCP server
            server_url: URL of the SSE endpoint (e.g. http://localhost:8001/sse)
        """
        self.server_name = server_name
        self.server_url = server_url
        self.session: Optional[ClientSession] = None
        self._sse_context = None
        
    async def connect(self):
        """Connect to the MCP server via SSE"""
        try:
            # Connect to SSE endpoint
            self._sse_context = sse_client(self.server_url)
            read_stream, write_stream = await self._sse_context.__aenter__()
            
            self.session = ClientSession(read_stream, write_stream)
            await self.session.initialize()
            
            logger.info(f"Connected to MCP server: {self.server_name} at {self.server_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.server_name} at {self.server_url}: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session:
            # MCP Session exit
            await self.session.__aexit__(None, None, None)
            self.session = None
        
        if self._sse_context:
            # SSE Context exit
            await self._sse_context.__aexit__(None, None, None)
            self._sse_context = None
            
        logger.info(f"Disconnected from MCP server: {self.server_name}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool
        
        Returns:
            Tool result
        """
        if not self.session:
            raise RuntimeError(f"Not connected to {self.server_name}")
        
        try:
            logger.info(f"Calling tool {tool_name} with args: {arguments}")
            result = await self.session.call_tool(tool_name, arguments)
            
            # Extract content from MCP result
            if hasattr(result, 'content') and result.content:
                # MCP returns content as a list of content items
                if isinstance(result.content, list) and len(result.content) > 0:
                    first_content = result.content[0]
                    if hasattr(first_content, 'text'):
                        import json
                        try:
                            return json.loads(first_content.text)
                        except:
                            return first_content.text
                    return first_content
                return result.content
            
            return result
        
        except Exception as e:
            logger.error(f"Tool call failed ({tool_name}): {e}", exc_info=True)
            raise
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.disconnect()



# Async wrapper for calling MCP tools
async def call_mcp_tool_async(server_url: str, tool_name: str, arguments: Dict[str, Any], timeout: int = 600) -> Any:
    """
    Async wrapper for calling MCP tools via SSE.
    """
    try:
        logger.info(f"Calling MCP tool: {tool_name} on {server_url}")
        
        async with asyncio.timeout(timeout):
            # Use sse_client directly as a context manager to avoid anyio scope issues
            async with sse_client(server_url) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(tool_name, arguments)
                    
                    # Extract content from MCP result (copied logic from MCPClient)
                    if hasattr(result, 'content') and result.content:
                        if isinstance(result.content, list) and len(result.content) > 0:
                            first_content = result.content[0]
                            if hasattr(first_content, 'text'):
                                import json
                                try:
                                    return json.loads(first_content.text)
                                except:
                                    return first_content.text
                            return first_content
                        return result.content
                    
                    logger.info(f"MCP tool {tool_name} completed successfully")
                    return result
                
    except asyncio.TimeoutError:
        logger.error(f"MCP tool call timed out after {timeout}s: {tool_name}")
        raise TimeoutError(f"MCP server call timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"MCP tool call failed: {tool_name} - {e}")
        raise


# Sync wrapper that works in both contexts
def call_mcp_tool_sync(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Sync wrapper for calling MCP tools. Works in both async and sync contexts.
    """
    import nest_asyncio
    nest_asyncio.apply()
    
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(call_mcp_tool_async(server_url, tool_name, arguments))


# Pre-configured clients for our MCP servers
# Note: Use internal Docker network names when running inside Docker,
# but 'localhost' works if ports are exposed and running locally.
# We'll use service names assuming this runs inside the cluster.

class VectorDBClient:
    """Client for Vector Database MCP server"""
    
    # SSE endpoint for Vector DB
    SERVER_URL = "http://vector-db-mcp:8001/sse"
    
    @staticmethod
    async def search_documents_async(query: str, top_k: int = 5, alpha: float = 0.7) -> dict:
        """Search documents using hybrid search (async)"""
        return await call_mcp_tool_async(
            VectorDBClient.SERVER_URL,
            "search_documents",
            {"query": query, "top_k": top_k, "alpha": alpha}
        )
    
    @staticmethod
    def search_documents(query: str, top_k: int = 5, alpha: float = 0.7) -> dict:
        """Search documents using hybrid search (sync)"""
        return call_mcp_tool_sync(
            VectorDBClient.SERVER_URL,
            "search_documents",
            {"query": query, "top_k": top_k, "alpha": alpha}
        )


class WebSearchClient:
    """Client for Web Search MCP server"""
    
    # SSE endpoint for Web Search
    SERVER_URL = "http://web-search-mcp:8002/sse"
    
    @staticmethod
    async def web_search_async(query: str, max_results: int = 5) -> dict:
        """Search the web using DuckDuckGo (async)"""
        return await call_mcp_tool_async(
            WebSearchClient.SERVER_URL,
            "web_search",
            {"query": query, "max_results": max_results}
        )
    
    @staticmethod
    def web_search(query: str, max_results: int = 5) -> dict:
        """Search the web using DuckDuckGo (sync)"""
        return call_mcp_tool_sync(
            WebSearchClient.SERVER_URL,
            "web_search",
            {"query": query, "max_results": max_results}
        )


class DocumentProcessingClient:
    """Client for Document Processing MCP server"""
    
    # SSE endpoint for Document Processing
    SERVER_URL = "http://document-mcp:8003/sse"
    
    @staticmethod
    async def process_document_async(file_path: str, filename: str) -> dict:
        """Process a document and store in vector database (async)"""
        return await call_mcp_tool_async(
            DocumentProcessingClient.SERVER_URL,
            "process_document",
            {"file_path": file_path, "filename": filename}
        )
    
    @staticmethod
    def process_document(file_path: str, filename: str) -> dict:
        """Process a document and store in vector database (sync)"""
        return call_mcp_tool_sync(
            DocumentProcessingClient.SERVER_URL,
            "process_document",
            {"file_path": file_path, "filename": filename}
        )
    
    @staticmethod
    async def get_supported_formats_async() -> dict:
        """Get list of supported document formats (async)"""
        return await call_mcp_tool_async(
            DocumentProcessingClient.SERVER_URL,
            "get_supported_formats",
            {}
        )
    
    @staticmethod
    def get_supported_formats() -> dict:
        """Get list of supported document formats (sync)"""
        return call_mcp_tool_sync(
            DocumentProcessingClient.SERVER_URL,
            "get_supported_formats",
            {}
        )

    @staticmethod
    async def list_documents_async() -> dict:
        """List all processed documents (async)"""
        return await call_mcp_tool_async(
            DocumentProcessingClient.SERVER_URL,
            "list_documents",
            {}
        )

    @staticmethod
    def list_documents() -> dict:
        """List all processed documents (sync)"""
        return call_mcp_tool_sync(
            DocumentProcessingClient.SERVER_URL,
            "list_documents",
            {}
        )

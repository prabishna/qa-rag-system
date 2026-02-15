from fastmcp import FastMCP
from backend.services.document_processor import document_processor
import os
import logging

logger = logging.getLogger(__name__)


mcp = FastMCP("Document Processing Server")

@mcp.tool()
def process_document(file_path: str, filename: str) -> dict:
    """
    Process a document (PDF, TXT, MD) and store in vector database.
    
    Args:
        file_path: Path to the document file
        filename: Name of the file
    
    Returns:
        dict: Processing result with document_id, num_chunks, status
    """
    try:
        logger.info(f"Starting processing for file: {filename} at {file_path}")
        if not os.path.exists(file_path):
            return {
                "status": "error",
                "message": f"File not found: {file_path}"
            }
        
        result = document_processor.process_document(file_path, filename)
        logger.info(f"Processing complete for {filename}: {result}")
        return result
    
    except Exception as e:
        logger.error(f"Document processing failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
def get_supported_formats() -> dict:
    """
    Get list of supported document formats.
    
    Returns:
        dict: Supported formats and their descriptions
    """
    return {
        "formats": {
            ".pdf": "PDF documents with OCR support for images",
            ".txt": "Plain text files",
            ".md": "Markdown files"
        }
    }

@mcp.tool()
def list_documents() -> dict:
    """
    List all processed documents in the uploads directory.
    
    Returns:
        dict: List of documents with metadata
    """
    try:
        import backend.database as database
        docs = database.list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return {
            "status": "error",
            "message": str(e),
            "documents": []
        }

@mcp.tool()
def delete_document(doc_id: str) -> dict:
    """
    Delete a document by its ID.
    Removes from metadata DB, vector DB, and file system.
    
    Args:
        doc_id: The document ID to delete
    
    Returns:
        dict: Deletion result with status and message
    """
    try:
        import backend.database as database
        
        # Get document info
        doc = database.get_document_by_id(doc_id)
        if not doc:
            return {
                "status": "error",
                "message": f"Document {doc_id} not found"
            }
        
        filename = doc["filename"]
        
        # Delete from vector database
        try:
            from backend.utils.mcp_client import VectorDatabaseClient
            vector_client = VectorDatabaseClient()
            expr = f'document_id == "{doc_id}"'
            vector_client.delete_documents(expr)
            logger.info(f"Deleted {doc_id} from vector database")
        except Exception as ve:
            logger.error(f"Failed to delete from vector DB: {ve}")
        
        # Delete from metadata database
        deleted = database.delete_document(doc_id)
        if not deleted:
            return {
                "status": "error",
                "message": f"Failed to delete {doc_id} from database"
            }
        
        # Delete physical file
        try:
            upload_dir = "uploads"
            file_path = os.path.join(upload_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
        except Exception as fe:
            logger.error(f"Failed to delete file: {fe}")
        
        return {
            "status": "success",
            "message": f"Successfully deleted document: {filename}",
            "document_id": doc_id
        }
    
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@mcp.tool()
def get_document_info(doc_id: str) -> dict:
    """
    Get detailed information about a specific document.
    
    Args:
        doc_id: The document ID to get information for
    
    Returns:
        dict: Document metadata including filename, size, chunks, etc.
    """
    try:
        import backend.database as database
        
        doc = database.get_document_by_id(doc_id)
        if not doc:
            return {
                "status": "error",
                "message": f"Document {doc_id} not found"
            }
        
        return {
            "status": "success",
            "document": doc
        }
    
    except Exception as e:
        logger.error(f"Error getting document info: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    # Run the MCP server with SSE transport
    mcp.run(transport='sse', port=8003, host='0.0.0.0')

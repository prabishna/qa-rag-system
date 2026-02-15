from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
import os
import shutil

from backend.agents.workflow import run_query
from backend.utils.mcp_client import DocumentProcessingClient
import backend.database as database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize metadata DB
try:
    database.init_db()
except Exception as e:
    logger.error(f"Failed to init metadata DB: {e}")

# Create FastAPI app
app = FastAPI(
    title="Advanced RAG System API",
    description="Multi-Agent RAG System with MCP Architecture, Hybrid Search, and Conversation Memory",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Request/Response models
class QueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    citations: List[dict]
    conversation_id: str
    used_web_search: bool
    query_type: str
    agent_trace: List[str]

class UploadResponse(BaseModel):
    status: str
    message: str
    document_id: Optional[str] = None
    num_chunks: Optional[int] = None
    filename: Optional[str] = None

# Health check
@app.get("/api/health")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Advanced RAG System with MCP Architecture",
        "version": "1.0.0",
        "mcp_servers": ["Document Processing", "Vector Database", "Web Search"]
    }

# Serve frontend
@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML"""
    return FileResponse("frontend/index.html")

@app.get("/styles.css")
async def serve_styles():
    return FileResponse("frontend/styles.css")

@app.get("/app.js")
async def serve_app_js():
    return FileResponse("frontend/app.js")

@app.get("/streaming-helpers.js")
async def serve_streaming_helpers():
    return FileResponse("frontend/streaming-helpers.js")

# Upload document endpoint
@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a document via Document Processing MCP server.
    
    The document will be:
    1. Saved to uploads directory
    2. Sent to Document Processing MCP server
    3. Processed, chunked, embedded, and stored in vector database
    """
    try:
        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        
        # Save file temporarily
        file_path = os.path.join("uploads", file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"File uploaded: {file.filename}")
    
        # Process document using MCP (via HTTP/SSE - safe for async)
        result = await DocumentProcessingClient.process_document_async(file_path, file.filename)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        # FAST FIX: Save to local metadata database so it appears in the list
        try:
            database.add_document(
                doc_id=result.get("document_id"),
                filename=result.get("filename"),
                file_size=os.path.getsize(file_path),
                num_chunks=result.get("num_chunks"),
                status="success"
            )
        except Exception as db_err:
            logger.error(f"Failed to save document metadata: {db_err}")
            # Don't fail the request, just log it
            
        return UploadResponse(
            filename=result.get("filename"),
            document_id=result.get("document_id"),
            num_chunks=result.get("num_chunks"),
            status="success",
            message=result.get("message", "Document processed successfully")
        )
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        # Clean up file on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))

# Query endpoint
@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Query the RAG system with optional conversation context.
    
    The system will:
    1. Analyze the query
    2. Retrieve relevant chunks (hybrid search)
    3. Re-rank results
    4. Generate answer with LLM
    5. Add citations
    6. Save to conversation history
    """
    try:
        logger.info(f"Query received: {request.query}")
        
        # Run through multi-agent workflow
        response = await run_query(
            query=request.query,
            conversation_id=request.conversation_id
        )
        
        # If this is a new conversation, generate a title in background
        if not request.conversation_id:
            new_id = response.get("conversation_id")
            if new_id:
                background_tasks.add_task(generate_chat_title, new_id, request.query)
        
        return QueryResponse(**response)
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_chat_title(thread_id: str, query: str):
    """Generate a short title for the conversation using LLM."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "Summarize the user's query into a concise 3-5 word title. Return ONLY the title."},
                {"role": "user", "content": query}
            ],
            max_tokens=15,
            temperature=0.3
        )
        title = response.choices[0].message.content.strip().strip('"')
        database.save_conversation_title(thread_id, title)
    except Exception as e:
        logger.error(f"Title generation failed: {e}")
        # Fallback
        database.save_conversation_title(thread_id, (query[:30] + "...") if len(query) > 30 else query)

# Streaming query endpoint (SSE)
@app.get("/documents")
async def list_documents():
    """List all uploaded documents from Metadata DB"""
    try:
        docs = database.list_documents()
        return {"documents": docs}
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return {"documents": []}

# Delete document endpoint
@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Delete a document by ID.
    Removes from metadata DB, vector DB, and file system.
    """
    try:
        # Get document info
        doc = database.get_document_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from vector database (Milvus)
        try:
            from backend.utils.mcp_client import VectorDatabaseClient
            vector_client = VectorDatabaseClient()
            
            # Delete all chunks for this document
            expr = f'document_id == "{doc_id}"'
            vector_client.delete_documents(expr)
            logger.info(f"Deleted document {doc_id} from vector database")
        except Exception as ve:
            logger.error(f"Failed to delete from vector DB: {ve}")
            # Continue with deletion even if vector DB fails
        
        # Delete from metadata database
        deleted = database.delete_document(doc_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete from database")
        
        # Delete physical file
        try:
            upload_dir = "uploads"
            file_path = os.path.join(upload_dir, doc["filename"])
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
        except Exception as fe:
            logger.error(f"Failed to delete file: {fe}")
            # Continue even if file deletion fails
        
        return {
            "status": "success",
            "message": f"Document {doc['filename']} deleted successfully",
            "document_id": doc_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Preview/download document endpoint
@app.get("/documents/{doc_id}/preview")
async def preview_document(doc_id: str):
    """
    Preview or download a document by ID.
    Returns the file with appropriate content-type.
    """
    try:
        # Get document info
        doc = database.get_document_by_id(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get file path
        upload_dir = "uploads"
        file_path = os.path.join(upload_dir, doc["filename"])
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Determine media type based on extension
        ext = doc["filename"].split('.')[-1].lower()
        media_types = {
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'md': 'text/markdown',
            'json': 'application/json'
        }
        media_type = media_types.get(ext, 'application/octet-stream')
        
        return FileResponse(
            file_path,
            media_type=media_type,
            filename=doc["filename"]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Stream query response in real-time using Server-Sent Events.
    Streams only the LLM generation part for better UX.
    
    Events:
    - start: Query processing started
    - status: Agent status updates  
    - token: Generated text tokens (word-by-word)
    - complete: Final result with citations
    - error: Error occurred
    """
    from fastapi.responses import StreamingResponse
    from backend.agents.streaming import stream_query_simple
    
    return StreamingResponse(
        stream_query_simple(request.query, request.conversation_id),
        media_type="text/event-stream"
    )

# Get conversation history
@app.get("/conversations")
async def list_conversations():
    """List all recent conversations from metadata DB"""
    try:
        conversations = database.get_conversations()
        return {"conversations": conversations}
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        return {"conversations": []}

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Get conversation history by ID.
    """
    try:
        # Use optimized database function for O(1) retrieval
        # instead of reconstructing from LangGraph state (O(N))
        history = database.get_conversation_messages(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "history": history
        }
    
    except Exception as e:
        logger.error(f"Failed to retrieve conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation by ID.
    Removes from metadata DB and messages DB.
    """
    try:
        deleted = database.delete_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found or failed to delete")
        
        return {
            "status": "success",
            "message": f"Conversation {conversation_id} deleted successfully",
            "conversation_id": conversation_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

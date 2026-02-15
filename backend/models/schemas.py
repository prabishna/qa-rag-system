from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# Document Upload Models
class DocumentUploadResponse(BaseModel):
    """Response after uploading a document"""
    document_id: str
    filename: str
    num_chunks: int
    status: str
    message: str

# Query Models
class QueryRequest(BaseModel):
    """User's question to the system"""
    query: str = Field(..., min_length=1, description="User's question")
    conversation_id: Optional[str] = Field(None, description="For follow-up questions")
    top_k: int = Field(default=5, description="Number of chunks to retrieve")

class Citation(BaseModel):
    """Source citation for an answer"""
    document_name: str
    page_number: Optional[int] = None
    chunk_text: str
    relevance_score: float

class QueryResponse(BaseModel):
    """Answer from the RAG system"""
    answer: str
    citations: List[Citation]
    conversation_id: str
    used_web_search: bool = False
    
# Document Chunk Model
class DocumentChunk(BaseModel):
    """A chunk of a document"""
    chunk_id: str
    document_id: str
    document_name: str
    chunk_text: str
    chunk_index: int
    page_number: Optional[int] = None
    metadata: dict = {}
    
# Conversation History
class ConversationTurn(BaseModel):
    """One Q&A turn in a conversation"""
    query: str
    answer: str
    citations: List[Citation]
    timestamp: datetime
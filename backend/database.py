
import sqlite3
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

DB_PATH = "rag_system.db"

def init_db():
    """Initialize the database with necessary tables."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create documents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                num_chunks INTEGER,
                status TEXT
            )
        """)

        # Create conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create messages table for fast retrieval
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
        
        # Create index on conversation_id for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages (conversation_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Re-raise to ensure we know if init fails
        raise e

def add_document(doc_id: str, filename: str, file_size: int, num_chunks: int, status: str = "success"):
    """Add a document record to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO documents (id, filename, file_size, num_chunks, status, upload_timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (doc_id, filename, file_size, num_chunks, status, datetime.now()))
        
        conn.commit()
        conn.close()
        logger.info(f"Document record added: {filename} ({doc_id})")
    except Exception as e:
        logger.error(f"Failed to add document record: {e}")

def save_conversation_title(thread_id: str, title: str):
    """Save or update a conversation title."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if exists to preserve created_at
        cursor.execute("SELECT id FROM conversations WHERE id = ?", (thread_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, thread_id))
        else:
            cursor.execute("INSERT INTO conversations (id, title) VALUES (?, ?)", (thread_id, title))
            
        conn.commit()
        conn.close()
        logger.info(f"Conversation title saved: {thread_id} -> {title}")
    except Exception as e:
        logger.error(f"Failed to save conversation title: {e}")

def save_message(conversation_id: str, role: str, content: str, citations: list = None):
    """Save a message to the conversation history."""
    try:
        import json
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        citations_json = json.dumps(citations) if citations else None
        
        cursor.execute("""
            INSERT INTO messages (conversation_id, role, content, citations)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, role, content, citations_json))
        
        # Ensure conversation exists in conversations table
        cursor.execute("INSERT OR IGNORE INTO conversations (id, title) VALUES (?, ?)", (conversation_id, "New Chat"))
        
        conn.commit()
        conn.close()
        logger.info(f"Message saved for conversation {conversation_id}")
    except Exception as e:
        logger.error(f"Failed to save message: {e}")

def get_conversation_messages(conversation_id: str):
    """Get all messages for a conversation."""
    try:
        import json
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT role, content, citations, created_at 
            FROM messages 
            WHERE conversation_id = ? 
            ORDER BY created_at ASC
        """, (conversation_id,))
        
        rows = cursor.fetchall()
        messages = []
        
        for row in rows:
            citations = []
            if row["citations"]:
                try:
                    citations = json.loads(row["citations"])
                except:
                    citations = []
            
            messages.append({
                "type": "user" if row["role"] == "user" else "assistant",
                "content": row["content"],
                "citations": citations,
                "created_at": row["created_at"]
            })
            
        conn.close()
        return messages
    except Exception as e:
        logger.error(f"Failed to get conversation messages: {e}")
        return []

def get_conversations(limit: int = 20):
    """Get list of recent conversations."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        conversations = []
        for row in rows:
            conversations.append({
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"]
            })
            
        conn.close()
        return conversations
    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        return []

def list_documents():
    """List all documents from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents ORDER BY upload_timestamp DESC")
        rows = cursor.fetchall()
        
        documents = []
        for row in rows:
            documents.append({
                "id": row["id"],
                "name": row["filename"],  # Frontend expects "name"
                "size": row["file_size"],
                "upload_time": row["upload_timestamp"],
                "chunks": row["num_chunks"],
                "type": row["filename"].split('.')[-1].upper() if '.' in row["filename"] else "UNKNOWN"
            })
            
        conn.close()
        return documents
    except Exception as e:
        logger.error(f"Failed to list documents from DB: {e}")
        return []

def get_document_by_id(doc_id: str):
    """Get a document by its ID."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "filename": row["filename"],
                "file_size": row["file_size"],
                "num_chunks": row["num_chunks"],
                "status": row["status"],
                "upload_timestamp": row["upload_timestamp"]
            }
        return None
    except Exception as e:
        logger.error(f"Failed to get document {doc_id}: {e}")
        return None

def delete_document(doc_id: str):
    """Delete a document record from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"Document record deleted: {doc_id}")
        else:
            logger.warning(f"Document not found for deletion: {doc_id}")
            
        return deleted
        return deleted
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id}: {e}")
        return False

def delete_conversation(conversation_id: str):
    """Delete a conversation and its messages."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Delete messages first (foreign key constraint might handle this if cascade is set, but better to be explicit)
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        
        # Delete conversation
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        if deleted:
            logger.info(f"Conversation deleted: {conversation_id}")
        else:
            logger.warning(f"Conversation not found for deletion: {conversation_id}")
            
        return deleted
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        return False

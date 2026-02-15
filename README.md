# Advanced Document Q&A RAG System

A production-ready Retrieval Augmented Generation (RAG) system with multi-agent architecture, hybrid search, and conversation memory.

## 🎯 Features

### **Multi-Agent Architecture (LangGraph)**
- **Orchestrator Agent** - Workflow coordination
- **Query Analysis Agent** - Intent classification & query optimization
- **Retrieval Agent** - Hybrid search (vector + keyword) with web fallback
- **Re-ranking Agent** - Cross-encoder scoring & diversity filtering
- **Generation Agent** - LLM-based answer synthesis
- **Citation Agent** - Source attribution & formatting

### **Advanced Search**
- **Hybrid Search** - 70% vector similarity + 30% keyword matching
- **Position-Aware PDF Extraction** - Using pdfplumber for layout preservation
- **OCR Support** - Extract text from images in PDFs
- **Web Search Fallback** - DuckDuckGo integration

### **Conversation Memory**
- **Persistent Storage** - SQLite-based conversation history
- **Context-Aware** - Follow-up questions with pronoun resolution
- **Thread-Based** - Unique conversation IDs

### **MCP Servers**
- **Document Processing MCP** - PDF, TXT, MD support
- **Vector Database MCP** - Milvus with hybrid search
- **Web Search MCP** - DuckDuckGo integration

## 🚀 Quick Start

### **1. Prerequisites**
```bash
# Python 3.11+
# Docker (for Milvus)
```

### **2. Install Dependencies**
```bash
uv sync
```

### **3. Environment Setup**
```bash
cp .env.example .env
# Edit .env with your OpenAI API key
```

### **4. Start Milvus**
```bash
docker-compose up -d
```

### **5. Start API Server**
```bash
uv run python backend/api/main.py
```

Server runs at: `http://localhost:8000`

### **6. Test the API**
```bash
# In another terminal
uv run python test_api.py
```

## 📡 API Endpoints

### **Health Check**
```http
GET /
```

### **Upload Document**
```http
POST /upload
Content-Type: multipart/form-data

file: <PDF/TXT/MD file>
```

**Response:**
```json
{
  "status": "success",
  "message": "Document processed successfully",
  "document_id": "uuid",
  "num_chunks": 42
}
```

### **Query**
```http
POST /query
Content-Type: application/json

{
  "query": "What is machine learning?",
  "conversation_id": "optional-uuid"
}
```

**Response:**
```json
{
  "answer": "Machine learning is...",
  "citations": [
    {
      "document_name": "ml_guide.pdf",
      "page_number": 5,
      "relevance_score": 0.85
    }
  ],
  "conversation_id": "uuid",
  "used_web_search": false,
  "query_type": "factual",
  "agent_trace": ["orchestrator", "query_analysis", "retrieval", ...]
}
```

### **Get Conversation**
```http
GET /conversations/{conversation_id}
```

## 🧪 Testing

### **Test Multi-Agent System**
```bash
uv run python test_agents.py
```

### **Test Conversation Memory**
```bash
uv run python test_conversation.py
```

### **Test SQLite Persistence**
```bash
uv run python test_sqlite_memory.py
```

### **Test API**
```bash
uv run python test_api.py
```

## 📁 Project Structure

```
RAG System/
├── backend/
│   ├── agents/           # Multi-agent system
│   │   ├── orchestrator.py
│   │   ├── query_analysis.py
│   │   ├── retrieval.py
│   │   ├── reranking.py
│   │   ├── generation.py
│   │   ├── citation.py
│   │   └── workflow.py
│   ├── api/              # FastAPI backend
│   │   └── main.py
│   ├── mcp_servers/      # MCP servers
│   │   ├── document_mcp.py
│   │   ├── vector_db_mcp.py
│   │   └── web_search_mcp.py
│   ├── models/           # Data models
│   ├── services/         # Business logic
│   └── utils/            # Utilities
├── conversations.db      # SQLite conversation storage
├── docker-compose.yml    # Milvus setup
└── requirements.txt
```

## 🔧 Configuration

Edit `.env`:

```env
# OpenAI
OPENAI_API_KEY=your-key-here
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
TEMPERATURE=0.7

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530
COLLECTION_NAME=document_chunks

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

## 🎯 Usage Examples

### **Example 1: Upload & Query**
```python
import requests

# Upload document
with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/upload",
        files={"file": f}
    )

# Query
response = requests.post(
    "http://localhost:8000/query",
    json={"query": "What is the main topic?"}
)

print(response.json()["answer"])
```

### **Example 2: Conversation**
```python
# First question
r1 = requests.post(
    "http://localhost:8000/query",
    json={"query": "What is OAuth 2.0?"}
)

conv_id = r1.json()["conversation_id"]

# Follow-up
r2 = requests.post(
    "http://localhost:8000/query",
    json={
        "query": "How does it work?",
        "conversation_id": conv_id
    }
)
# System resolves "it" → "OAuth 2.0"
```

## 🏗️ Architecture

```
User Query
    ↓
Orchestrator (initialize)
    ↓
Query Analysis (classify & optimize)
    ↓
Retrieval (hybrid search + web fallback)
    ↓
Re-ranking (cross-encoder scoring)
    ↓
Generation (LLM synthesis)
    ↓
Citation (source attribution)
    ↓
Final Answer + Citations
```

## 📊 Tech Stack

- **Framework**: LangGraph
- **API**: FastAPI
- **Vector DB**: Milvus
- **LLM**: OpenAI GPT-4o-mini
- **Embeddings**: text-embedding-3-small
- **Memory**: SQLite
- **PDF Processing**: pdfplumber
- **OCR**: pytesseract
- **Web Search**: DuckDuckGo

## 🚀 Production Deployment

1. **Use PostgreSQL** for conversation storage
2. **Add authentication** to API endpoints
3. **Configure CORS** appropriately
4. **Use Redis** for caching
5. **Add rate limiting**
6. **Monitor with logging**

## 📝 License

MIT

## 🤝 Contributing

Contributions welcome!

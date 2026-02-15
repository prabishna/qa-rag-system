# Document Q&A RAG System

A multi-agent AI system that reads your documents and answers questions about them with high accuracy.

It uses **LangGraph** to coordinate agents, **Milvus** to search your files, and **OpenAI** to generate answers.

## Key Features

*   **Smart Search:** Uses both keyword and AI search (Hybrid Search) to find the exact text you need.
*   **Chat Memory:** Remembers your conversation so you can ask follow-up questions.
*   **Citations:** Every answer shows exactly which document and page it came from.
*   **Streaming:** Answers appear word-by-word, just like ChatGPT.

## Tech Stack

*   **Backend:** Python (FastAPI)
*   **AI Orchestration:** LangGraph
*   **Vector Database:** Milvus
*   **LLM:** OpenAI GPT-4o-mini
*   **Tools:** Model Context Protocol (MCP) servers for modularity.

---

##  Quick Start

Run the entire system with Docker. No complex setup required.

### 1. Requirements

*   Docker installed.
*   An OpenAI API Key.

### 2. Setup

Create a `.env` file with your API key:

```bash
# Create .env file
cp .env.example .env
```

Edit `.env` and add your key:
```env
OPENAI_API_KEY=sk-your-key-here...
```

### 3. Run

Start everything with one command:

```bash
docker-compose up --build -d
```

### 4. Use It

Open your browser to **http://localhost:8000**.

1.  Upload a PDF document.
2.  Start asking questions!

---

## How It Works

When you ask a question:
1.  **AI Agents** analyze if you need to look up a document or search the web.
2.  **Hybrid Search** finds the most relevant chunks of text from your uploaded files.
3.  **Cross-Encoder** re-ranks them to pick the very best matches.
4.  **GPT-4** writes an answer using *only* those facts and adds citations.

---

## Testing

To run backend tests locally:

```bash
# Install dependencies
uv sync

# Run tests
uv run python main.py
```


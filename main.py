"""
Advanced RAG System - Main Entry Point
"""
import uvicorn
from backend.api.main import app

def main():
    """Start the FastAPI application"""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

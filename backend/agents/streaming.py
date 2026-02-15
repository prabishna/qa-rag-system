"""
Simple streaming implementation - streams only the LLM generation part.
Uses OpenAI streaming + FastAPI SSE.
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from backend.agents.workflow import run_query
from backend.agents.state import create_initial_state
from backend.agents.orchestrator import orchestrator_agent
from backend.agents.query_analysis import query_analysis_agent
from backend.agents.retrieval import retrieval_agent
from backend.agents.reranking import reranking_agent
from backend.agents.citation import citation_agent
from backend.config import settings
import backend.database as database
from openai import AsyncOpenAI
import json
import logging
import uuid

logger = logging.getLogger(__name__)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

GENERATION_PROMPT = """You are an expert assistant. Generate a comprehensive, accurate answer based on the provided context.

User Query: {query}

Context from Retrieved Sources:
{context}

Instructions:
1. Answer the question directly and comprehensively
2. Use ONLY information from the provided context
3. Be factual and precise
4. Structure your answer clearly

Generate a well-structured answer:
"""

async def stream_query_simple(query: str, conversation_id: str = None):
    """
    Stream query response - runs all agents, streams only LLM generation.
    Yields SSE-formatted events.
    """
    try:
        # Generate thread ID
        thread_id = conversation_id or str(uuid.uuid4())
        
        # Save user query IMMEDIATELY to ensure conversation is created
        try:
            database.save_message(
                conversation_id=thread_id,
                role="user",
                content=query
            )
            logger.info(f"User message saved for {thread_id}")
            
            # If this is a new conversation (no ID passed), generate and save a title immediately
            if not conversation_id:
                # Use simple title first
                title = (query[:30] + "...") if len(query) > 30 else query
                database.save_conversation_title(thread_id, title)
                # We can update it with LLM later if needed, but this ensures it exists
        except Exception as db_err:
            logger.error(f"Failed to save initial message: {db_err}")

        # Send start event
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': thread_id})}\n\n"
        
        # Create initial state
        state = create_initial_state(query, thread_id)
        
        # Run agents (non-streaming)
        yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing query...'})}\n\n"
        state = orchestrator_agent(state)
        state = query_analysis_agent(state)
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Searching documents...'})}\n\n"
        state = await retrieval_agent(state)
        
        yield f"data: {json.dumps({'type': 'status', 'message': 'Ranking results...'})}\n\n"
        state = reranking_agent(state)
        
        # Prepare context for generation
        reranked_chunks = state.get("reranked_chunks", [])
        context_parts = []
        for idx, chunk in enumerate(reranked_chunks[:5], 1):
            context_parts.append(
                f"[{idx}] {chunk.get('document_name', 'Unknown')}\n{chunk.get('chunk_text', '')}\n"
            )
        context = "\n".join(context_parts)
        
        # Stream generation
        yield f"data: {json.dumps({'type': 'status', 'message': 'Generating answer...'})}\n\n"
        
        full_answer = ""
        stream = await openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": GENERATION_PROMPT.format(query=query, context=context)}
            ],
            temperature=settings.temperature,
            max_tokens=800,
            stream=True
        )
        
        # Stream tokens
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_answer += content
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
        
        state["answer"] = full_answer
        
        # Add citations
        state = citation_agent(state)
        
        # Send final result
        citations_data = [
            {
                "document_name": c.document_name,
                "page_number": c.page_number,
                "chunk_text": c.chunk_text[:200],
                "relevance_score": c.relevance_score
            }
            for c in state.get("citations", [])
        ]
        
        yield f"data: {json.dumps({'type': 'complete', 'citations': citations_data, 'conversation_id': thread_id, 'query_type': state.get('query_type'), 'used_web_search': state.get('used_web_search', False)})}\n\n"
        
        # Save assistant response to database
        try:
            database.save_message(
                conversation_id=thread_id,
                role="assistant",
                content=full_answer,
                citations=citations_data
            )
            logger.info(f"Assistant response saved for {thread_id}")
            
            # Optionally improve title using LLM in background if it was new?
            # For now simple title is fine.
                
        except Exception as e:
            logger.error(f"Failed to save assistant response to DB: {e}")

        
    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

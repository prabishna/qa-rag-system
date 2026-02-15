from backend.agents.state import AgentState
from backend.config import settings
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.openai_api_key)

GENERATION_PROMPT = """You are an expert assistant. Generate a comprehensive, accurate answer based on the provided context.

{conversation_context}

User Query: {query}

Context from Retrieved Sources:
{context}

Instructions:
1. Answer the question directly and comprehensively
2. Use ONLY information from the provided context
3. If this is a follow-up question, maintain coherence with previous conversation
4. If the context is insufficient, acknowledge the limitations
5. Be factual and precise
6. Structure your answer clearly with paragraphs
7. Reference sources using [1], [2], etc. notation where appropriate
8. If comparing items, provide balanced analysis

Generate a well-structured answer:
"""

def generation_agent(state: AgentState) -> AgentState:
    """
    Generation Agent - Generates comprehensive answer from context.
    
    Responsibilities:
    - Format context from re-ranked chunks
    - Generate answer using LLM
    - Maintain factual accuracy
    - Include reasoning
    
    Args:
        state: Current agent state
    
    Returns:
        AgentState: Updated state with generated answer
    """
    logger.info(f"Generation: Generating answer from {len(state['reranked_chunks'])} chunks")
    
    # Add to trace
    state["agent_trace"].append("generation")
    
    chunks = state["reranked_chunks"]
    query = state["query"]
    
    # Check if this is a general question/small talk that doesn't require documents
    is_general_query = any([
        len(query.split()) <= 3,  # Very short queries like "hi", "hello", "how are you"
        query.lower().strip() in ["hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye"],
        query.lower().startswith(("hi ", "hello ", "hey ", "how are you", "what's up", "good morning", "good afternoon", "good evening")),
    ])
    
    if not chunks and not is_general_query:
        logger.warning("Generation: No chunks available for generation")
        state["answer"] = "I don't have enough information to answer this question. Please try uploading relevant documents or rephrasing your query."
        state["reasoning"] = "No relevant context found"
        return state
    
    # If no chunks but it's a general query, answer naturally
    if not chunks and is_general_query:
        try:
            response = openai_client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": "You are SourceMind AI, a helpful and friendly AI assistant. Respond naturally to greetings and general questions. Keep responses concise and warm."},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=150
            )
            state["answer"] = response.choices[0].message.content
            state["reasoning"] = "Responded to general query without document context"
            logger.info("Generation: Responded to general query")
            return state
        except Exception as e:
            logger.error(f"Generation: Error during general query response: {e}")
            state["answer"] = "Hello! How can I help you today?"
            state["reasoning"] = f"Error: {str(e)}"
            return state
    
    # Format context from documents
    context_parts = []
    for idx, chunk in enumerate(chunks, 1):
        source = chunk.get("document_name", "Unknown")
        page = chunk.get("page_number")
        text = chunk.get("chunk_text", "")
        
        page_info = f", page {page}" if page else ""
        context_parts.append(f"[{idx}] From {source}{page_info}:\n{text}\n")
    
    context = "\n".join(context_parts)
    
    # LangGraph's memory system handles conversation context automatically
    conversation_context = "\nNo previous conversation context.\n"
    
    try:
        # Generate answer
        response = openai_client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful, accurate assistant that answers questions based on provided context."},
                {"role": "user", "content": GENERATION_PROMPT.format(
                    query=state["query"],
                    context=context,
                    conversation_context=conversation_context
                )}
            ],
            temperature=settings.temperature,
            max_tokens=800
        )
        
        answer = response.choices[0].message.content
        state["answer"] = answer
        
        # Extract reasoning (simplified)
        state["reasoning"] = f"Generated answer from {len(chunks)} relevant sources"
        
        logger.info(f"Generation: Successfully generated answer ({len(answer)} chars)")
        
    except Exception as e:
        logger.error(f"Generation: Error during answer generation: {e}")
        state["answer"] = "I encountered an error while generating the answer. Please try again."
        state["reasoning"] = f"Error: {str(e)}"
    
    return state

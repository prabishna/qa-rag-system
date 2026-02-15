from backend.agents.state import AgentState
from backend.config import settings
from openai import OpenAI
import logging
import numpy as np

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.openai_api_key)

def get_embeddings_batch(texts: list[str]) -> list[np.ndarray]:
    """Get embeddings for a list of texts in a single batch call."""
    try:
        if not texts:
            return []
            
        # openai's input can be a list of strings
        response = openai_client.embeddings.create(
            model=settings.embedding_model,
            input=texts
        )
        
        # Sort by index to ensure order matches input
        data = sorted(response.data, key=lambda x: x.index)
        return [np.array(d.embedding) for d in data]
    except Exception as e:
        logger.error(f"Error generating embeddings batch: {e}")
        return []

def calculate_cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Calculate cosine similarity between two embedding vectors."""
    try:
        if emb1 is None or emb2 is None:
            return 0.0
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))
    except Exception:
        return 0.0

def reranking_agent(state: AgentState) -> AgentState:
    """
    Re-ranking Agent - Re-scores and prioritizes retrieved chunks due to diversity.
    
    Responsibilities:
    - Re-rank chunks using cross-encoder approach (simplified)
    - Filter low-quality results
    - Ensure diversity (remove near-duplicates) by comparing embeddings
    - Select top-k for generation
    """
    logger.info(f"Re-ranking: Starting re-ranking of {len(state['retrieved_chunks'])} chunks")
    
    state["agent_trace"].append("reranking")
    
    chunks = state["retrieved_chunks"]
    if not chunks:
        logger.warning("Re-ranking: No chunks to re-rank")
        state["reranked_chunks"] = []
        return state
    
    query = state["optimized_query"] or state["query"]
    
    # Step 1: Initial scoring (keywords/relevance)
    reranked = []
    for chunk in chunks:
        try:
            base_score = chunk.get("combined_score", 0.5)
            
            if chunk.get("source_type") == "document":
                query_words = set(query.lower().split())
                chunk_text_lower = chunk["chunk_text"].lower()
                chunk_words = set(chunk_text_lower.split())
                
                # Simple keyword overlap
                keyword_overlap = len(query_words & chunk_words) / max(len(query_words), 1)
                
                # Boost if exact phrase match
                phrase_boost = 0.2 if query.lower() in chunk_text_lower else 0.0
                
                final_score = 0.5 * base_score + 0.3 * keyword_overlap + 0.2 * phrase_boost
            else:
                final_score = base_score * 0.9
            
            chunk["rerank_score"] = final_score
            reranked.append(chunk)
            
        except Exception as e:
            logger.error(f"Re-ranking: Error scoring chunk: {e}")
            chunk["rerank_score"] = chunk.get("combined_score", 0.5)
            reranked.append(chunk)
    
    # Step 2: Sort by score
    reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
    
    # Optimize: Only consider top N for diversity check to save tokens if list is huge
    # But usually retrieved_chunks is small (~10-20), so we can process all.
    candidates = reranked[:20] 
    
    # Step 3: Batch Embeddings for Diversity Check
    # We need embeddings for all candidates to compare them
    # To save time, we prepare a single batch request
    logger.info(f"Re-ranking: Generating embeddings for {len(candidates)} candidates in batch")
    
    candidate_texts = [c["chunk_text"][:1000] for c in candidates] # Limit text length for embedding
    
    embeddings = get_embeddings_batch(candidate_texts)
    
    # Attach embeddings to chunks temporarily (match by index)
    if len(embeddings) == len(candidates):
        for i, emb in enumerate(embeddings):
            candidates[i]["embedding"] = emb
    else:
        logger.error("Mismatch in embedding batch size, skipping diversity check")
        for c in candidates:
            c["embedding"] = None

    # Step 4: Diversity filtering
    diverse_chunks = []
    similarity_threshold = 0.85 # Slightly lower threshold since embeddings are better
    
    top_k = state["search_params"].get("top_k", 5)
    
    for chunk in candidates:
        if len(diverse_chunks) >= top_k:
            break
            
        is_duplicate = False
        chunk_emb = chunk.get("embedding")
        
        # If we have embeddings, check similarity
        if chunk_emb is not None:
            for selected in diverse_chunks:
                selected_emb = selected.get("embedding")
                if selected_emb is not None:
                    sim = calculate_cosine_similarity(chunk_emb, selected_emb)
                    if sim > similarity_threshold:
                        is_duplicate = True
                        logger.debug(f"Re-ranking: Filtered duplicate (sim: {sim:.2f})")
                        break
        
        if not is_duplicate:
            # Clean up embedding before adding to state (not JSON serializable usually, and not needed later)
            # But we keep it for the loop. We'll strip it at the end.
            diverse_chunks.append(chunk)
    
    # Cleanup embeddings from objects in state
    final_chunks = []
    for c in diverse_chunks:
        c_copy = c.copy()
        if "embedding" in c_copy:
            del c_copy["embedding"]
        final_chunks.append(c_copy)
    
    state["reranked_chunks"] = final_chunks
    logger.info(f"Re-ranking: Selected {len(final_chunks)} diverse chunks")
    
    return state

from backend.agents.state import AgentState
from backend.models.schemas import Citation
import logging
import re

logger = logging.getLogger(__name__)

def citation_agent(state: AgentState) -> AgentState:
    """
    Citation Agent - Adds citations and verifies sources.
    
    Responsibilities:
    - Extract citation markers from answer
    - Map citations to source chunks
    - Add metadata (document, page, score)
    - Format citations properly
    
    Args:
        state: Current agent state
    
    Returns:
        AgentState: Updated state with formatted citations
    """
    logger.info(f"Citation: Adding citations to answer")
    
    # Add to trace
    state["agent_trace"].append("citation")
    
    answer = state.get("answer", "")
    chunks = state.get("reranked_chunks", [])
    
    if not chunks:
        logger.warning("Citation: No chunks available for citations")
        state["citations"] = []
        return state
    
    # Extract citation numbers from answer [1], [2], etc.
    citation_pattern = r'\[(\d+)\]'
    cited_numbers = set(re.findall(citation_pattern, answer))
    
    citations = []
    
    # Create citation objects for each cited source
    for idx, chunk in enumerate(chunks, 1):
        # Only create citation if it's referenced in the answer
        if str(idx) in cited_numbers or not cited_numbers:  # If no citations found, cite all sources
            try:
                citation = Citation(
                    document_name=chunk.get("document_name", "Unknown Source"),
                    page_number=chunk.get("page_number"),
                    chunk_text=chunk.get("chunk_text", "")[:200],  # First 200 chars as excerpt
                    relevance_score=chunk.get("rerank_score", chunk.get("combined_score", 0.0))
                )
                
                # Add URL for web sources
                if chunk.get("source_type") == "web":
                    citation.url = chunk.get("url")
                
                citations.append(citation)
                
            except Exception as e:
                logger.error(f"Citation: Error creating citation for chunk {idx}: {e}")
    
    state["citations"] = citations
    
    logger.info(f"Citation: Added {len(citations)} citations")
    
    # If no citation markers were found in the answer, append citation list
    if not cited_numbers and citations:
        citation_text = "\n\nSources:\n"
        for idx, citation in enumerate(citations, 1):
            page_info = f", page {citation.page_number}" if citation.page_number else ""
            score_info = f" (relevance: {citation.relevance_score:.2f})"
            
            if hasattr(citation, 'url') and citation.url:
                citation_text += f"[{idx}] {citation.document_name}{page_info}{score_info}\n    URL: {citation.url}\n"
            else:
                citation_text += f"[{idx}] {citation.document_name}{page_info}{score_info}\n"
        
        state["answer"] = answer + citation_text
    
    return state

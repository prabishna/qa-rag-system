from typing import List, Dict, Optional
from datetime import datetime
from backend.models.schemas import ConversationTurn, Citation
import json
import os
import logging

logger = logging.getLogger(__name__)

class ConversationMemory:
    """
    Manages conversation history and context for multi-turn conversations.
    Stores conversation turns in memory with optional persistence.
    """
    
    def __init__(self, storage_dir: str = "conversations"):
        """
        Initialize conversation memory.
        
        Args:
            storage_dir: Directory to store conversation history
        """
        self.storage_dir = storage_dir
        self.conversations: Dict[str, List[ConversationTurn]] = {}
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_dir, exist_ok=True)
        
        logger.info(f"ConversationMemory initialized with storage: {storage_dir}")
    
    def add_turn(
        self,
        conversation_id: str,
        query: str,
        answer: str,
        citations: List[Citation]
    ) -> None:
        """
        Add a conversation turn to history.
        
        Args:
            conversation_id: Unique conversation identifier
            query: User's question
            answer: System's answer
            citations: List of citations
        """
        turn = ConversationTurn(
            query=query,
            answer=answer,
            citations=citations,
            timestamp=datetime.now()
        )
        
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        self.conversations[conversation_id].append(turn)
        
        logger.info(f"Added turn to conversation {conversation_id}. Total turns: {len(self.conversations[conversation_id])}")
        
        # Persist to disk
        self._save_conversation(conversation_id)
    
    def get_history(
        self,
        conversation_id: str,
        max_turns: int = 10
    ) -> List[ConversationTurn]:
        """
        Get conversation history.
        
        Args:
            conversation_id: Unique conversation identifier
            max_turns: Maximum number of recent turns to return
        
        Returns:
            List of conversation turns (most recent first)
        """
        if conversation_id not in self.conversations:
            # Try to load from disk
            self._load_conversation(conversation_id)
        
        history = self.conversations.get(conversation_id, [])
        
        # Return most recent turns
        return history[-max_turns:] if history else []
    
    def get_context_summary(
        self,
        conversation_id: str,
        max_turns: int = 5
    ) -> str:
        """
        Get a formatted summary of recent conversation context.
        
        Args:
            conversation_id: Unique conversation identifier
            max_turns: Maximum number of recent turns to include
        
        Returns:
            Formatted context string
        """
        history = self.get_history(conversation_id, max_turns)
        
        if not history:
            return ""
        
        context_parts = ["Previous conversation context:"]
        
        for idx, turn in enumerate(history, 1):
            context_parts.append(f"\nTurn {idx}:")
            context_parts.append(f"User: {turn.query}")
            context_parts.append(f"Assistant: {turn.answer[:200]}...")  # First 200 chars
        
        return "\n".join(context_parts)
    
    def clear_conversation(self, conversation_id: str) -> None:
        """
        Clear conversation history.
        
        Args:
            conversation_id: Unique conversation identifier
        """
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
        
        # Delete from disk
        filepath = os.path.join(self.storage_dir, f"{conversation_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
        
        logger.info(f"Cleared conversation {conversation_id}")
    
    def _save_conversation(self, conversation_id: str) -> None:
        """Save conversation to disk."""
        try:
            filepath = os.path.join(self.storage_dir, f"{conversation_id}.json")
            
            turns_data = []
            for turn in self.conversations.get(conversation_id, []):
                turns_data.append({
                    "query": turn.query,
                    "answer": turn.answer,
                    "citations": [
                        {
                            "document_name": c.document_name,
                            "page_number": c.page_number,
                            "chunk_text": c.chunk_text,
                            "relevance_score": c.relevance_score
                        }
                        for c in turn.citations
                    ],
                    "timestamp": turn.timestamp.isoformat()
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(turns_data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error saving conversation {conversation_id}: {e}")
    
    def _load_conversation(self, conversation_id: str) -> None:
        """Load conversation from disk."""
        try:
            filepath = os.path.join(self.storage_dir, f"{conversation_id}.json")
            
            if not os.path.exists(filepath):
                return
            
            with open(filepath, 'r', encoding='utf-8') as f:
                turns_data = json.load(f)
            
            turns = []
            for turn_data in turns_data:
                citations = [
                    Citation(**c) for c in turn_data.get("citations", [])
                ]
                
                turn = ConversationTurn(
                    query=turn_data["query"],
                    answer=turn_data["answer"],
                    citations=citations,
                    timestamp=datetime.fromisoformat(turn_data["timestamp"])
                )
                turns.append(turn)
            
            self.conversations[conversation_id] = turns
            logger.info(f"Loaded conversation {conversation_id} with {len(turns)} turns")
            
        except Exception as e:
            logger.error(f"Error loading conversation {conversation_id}: {e}")


# Global conversation memory instance
conversation_memory = ConversationMemory()

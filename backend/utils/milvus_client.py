from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from backend.config import settings
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class MilvusClient:
    def __init__(self):
        self.collection_name = "document_chunks"
        self.dimension = 1536  # OpenAI text-embedding-3-small dimension
        self.connect()
        self.create_collection()
    
    def connect(self):
        """Connect to Milvus"""
        try:
            connections.connect(
                alias="default",
                host=settings.milvus_host,
                port=settings.milvus_port
            )
            logger.info(f"Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def create_collection(self):
        """Create collection if it doesn't exist"""
        if utility.has_collection(self.collection_name):
            logger.info(f"Collection '{self.collection_name}' already exists")
            self.collection = Collection(self.collection_name)
            return
        
        # Define schema
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="document_name", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="chunk_text", dtype=DataType.VARCHAR, max_length=5000),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="page_number", dtype=DataType.INT64),
        ]
        
        schema = CollectionSchema(fields=fields, description="Document chunks with embeddings")
        self.collection = Collection(name=self.collection_name, schema=schema)
        
        # Create index for vector search
        index_params = {
            "metric_type": "COSINE",  # Cosine similarity
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        self.collection.create_index(field_name="embedding", index_params=index_params)
        logger.info(f"Created collection '{self.collection_name}' with index")
    
    def insert_chunks(self, data):
        """
        Insert document chunks with embeddings.
        
        Args:
            data: Can be a list of dicts (rows) or a dict of lists (columns).
                  If dict of lists, it must contain keys matching the schema fields.
        """
        try:
            # Check if input is a dict of lists (columnar format)
            if isinstance(data, dict):
                # Convert to list of lists in the order of schema fields
                insert_data = [
                    data["chunk_id"],
                    data["embedding"],
                    data["document_id"],
                    data["document_name"],
                    data["chunk_text"],
                    data["chunk_index"],
                    data["page_number"]
                ]
                self.collection.insert(insert_data)
                self.collection.flush()
                logger.info(f"Inserted {len(data['chunk_id'])} chunks into Milvus")
            
            # Check if input is a list of dicts (row format)
            elif isinstance(data, list) and isinstance(data[0], dict):
                # Convert list of dicts to list of lists
                # This is less efficient but supports row-based input
                insert_data = [
                    [row["chunk_id"] for row in data],
                    [row["embedding"] for row in data],
                    [row["document_id"] for row in data],
                    [row["document_name"] for row in data],
                    [row["chunk_text"] for row in data],
                    [row["chunk_index"] for row in data],
                    [row["page_number"] for row in data]
                ]
                self.collection.insert(insert_data)
                self.collection.flush()
                logger.info(f"Inserted {len(data)} chunks into Milvus")
                
            else:
                # Assume it's already in list of lists format
                self.collection.insert(data)
                self.collection.flush()
                logger.info("Inserted chunks into Milvus (list format)")
                
        except Exception as e:
            logger.error(f"Failed to insert chunks into Milvus: {e}")
            raise
    
    def search(self, query_embedding: List[float], top_k: int = 5):
        """Search for similar chunks using vector similarity"""
        self.collection.load()
        
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["chunk_id", "document_name", "chunk_text", "page_number"]
        )
        
        return results[0]  # Return first query results
    
    def hybrid_search(self, query_embedding: List[float], query_text: str, top_k: int = 5, alpha: float = 0.7):
        """
        Hybrid search combining vector similarity and keyword matching.
        
        Args:
            query_embedding: Vector embedding of the query
            query_text: Original query text for keyword matching
            top_k: Number of results to return
            alpha: Weight for vector search (1-alpha for keyword). Default 0.7 means 70% vector, 30% keyword
        
        Returns:
            List of search results with combined scores
        """
        self.collection.load()
        
        # 1. Vector search (semantic similarity)
        vector_search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        vector_results = self.collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=vector_search_params,
            limit=top_k * 2,  # Get more results for reranking
            output_fields=["chunk_id", "document_name", "chunk_text", "page_number"]
        )
        
        # 2. Keyword search (BM25-like scoring)
        # Extract keywords from query
        keywords = query_text.lower().split()
        
        # Score each result based on keyword matches
        hybrid_results = []
        for hit in vector_results[0]:
            chunk_text = hit.entity.get("chunk_text", "").lower()
            
            # Calculate keyword score (simple TF-IDF approximation)
            keyword_score = 0
            for keyword in keywords:
                if keyword in chunk_text:
                    # Count occurrences
                    count = chunk_text.count(keyword)
                    # Simple TF score
                    keyword_score += count / len(chunk_text.split())
            
            # Normalize keyword score to 0-1 range
            keyword_score = min(keyword_score, 1.0)
            
            # Combine scores: alpha * vector_score + (1-alpha) * keyword_score
            vector_score = hit.score
            combined_score = alpha * vector_score + (1 - alpha) * keyword_score
            
            hybrid_results.append({
                "hit": hit,
                "vector_score": vector_score,
                "keyword_score": keyword_score,
                "combined_score": combined_score
            })
        
        # Sort by combined score (descending)
        hybrid_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Return top_k results
        return hybrid_results[:top_k]

# Global instance
milvus_client = MilvusClient()

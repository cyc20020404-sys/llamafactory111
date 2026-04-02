"""
Configuration management for RAG backend
"""
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Qdrant settings
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "chat_chunks"
    
    # Embedding settings
    embedding_model: str = "text2vec-base-chinese"
    embedding_device: str = "cpu"
    vector_dimension: int = 768
    
    # Chunking settings
    chunk_size: int = 300
    chunk_overlap: int = 20
    
    # RAG settings
    top_k: int = 5
    
    # RAG retrieval optimization settings
    rag_hybrid_alpha: float = 0.5  # 0.0 = full keyword (BM25), 1.0 = full vector
    min_similarity_threshold: float = 0.05  # Minimum similarity score for RAG usage
    rag_fallback_to_full_context: bool = True  # Enable fallback when similarity is low
    rag_enable_boost_keywords: bool = True  # Enable keyword boosting
    
    # RAG indexing settings
    rag_index_user_only: bool = True  # Only index user messages (better retrieval)
    rag_incremental_index: bool = True  # Enable incremental indexing
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()

# Export settings instance
settings = get_settings()

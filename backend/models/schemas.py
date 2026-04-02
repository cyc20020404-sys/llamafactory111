"""
Pydantic schemas for API request/response models
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class Message(BaseModel):
    """Single chat message"""
    id: str = Field(..., description="Unique message ID")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="Message timestamp")

class ChatHistory(BaseModel):
    """Chat history for indexing"""
    chat_id: str = Field(..., description="Unique chat session ID")
    messages: List[Message] = Field(..., description="List of messages in the chat")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class ChatHistoryIndexRequest(BaseModel):
    """Request to index chat history"""
    chat_id: str = Field(..., description="Unique chat session ID")
    messages: List[Message] = Field(..., description="List of messages to index")
    reindex: bool = Field(default=False, description="Reindex existing chat")

class ChatHistoryIndexResponse(BaseModel):
    """Response after indexing chat history"""
    status: str = Field(..., description="Indexing status")
    chat_id: str = Field(..., description="Indexed chat ID")
    chunks_count: int = Field(..., description="Number of chunks created")
    message: Optional[str] = Field(None, description="Additional message")

class RAGQueryRequest(BaseModel):
    """RAG query request"""
    query: str = Field(..., description="User query")
    chat_id: Optional[str] = Field(None, description="Filter by specific chat ID")
    top_k: Optional[int] = Field(default=5, description="Number of context chunks to retrieve")
    include_context: bool = Field(default=True, description="Include retrieved context in response")

class RAGQueryResponse(BaseModel):
    """RAG query response"""
    query: str = Field(..., description="Original query")
    enhanced_prompt: str = Field(..., description="Prompt with RAG context")
    retrieved_contexts: Optional[List[Dict[str, Any]]] = Field(None, description="Retrieved context chunks")
    context_count: int = Field(..., description="Number of contexts retrieved")
    quality_info: Optional[Dict[str, Any]] = Field(None, description="Retrieval quality analysis")

class RAGStatsResponse(BaseModel):
    """RAG system statistics"""
    collection: str = Field(..., description="Collection name")
    vectors_count: int = Field(..., description="Total vectors stored")
    points_count: int = Field(..., description="Total points stored")
    status: str = Field(..., description="Collection status")

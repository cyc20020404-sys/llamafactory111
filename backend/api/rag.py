"""
RAG API endpoints with enhanced retrieval strategies
Features:
- Hybrid search (vector + keyword)
- Fallback strategy based on similarity threshold
- Quality scoring for retrieved contexts
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from models.schemas import (
    ChatHistoryIndexRequest,
    ChatHistoryIndexResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGStatsResponse
)
from core.embeddings import get_embedding_service
from services.chunker import get_chunker
from services.vector_store import get_vector_store
from core.config import get_settings

router = APIRouter()
settings = get_settings()


class RetrievalQualityAnalyzer:
    """Analyzes retrieval quality and determines fallback strategy"""

    def __init__(self, min_threshold: float = None):
        self.min_threshold = min_threshold or settings.min_similarity_threshold

    def analyze(
        self,
        results: List[dict],
        query: str
    ) -> dict:
        """
        Analyze retrieval results and determine quality level.

        Returns:
            dict with:
                - quality_level: "high", "medium", "low", "none"
                - should_use_rag: bool
                - fallback_strategy: str
                - confidence_score: float (0-1)
                - best_score: float
                - avg_score: float
        """
        if not results:
            return {
                "quality_level": "none",
                "should_use_rag": False,
                "fallback_strategy": "no_context",
                "confidence_score": 0.0,
                "best_score": 0.0,
                "avg_score": 0.0,
                "total_results": 0
            }

        scores = [r.get('score', 0.0) for r in results]
        best_score = max(scores)
        avg_score = sum(scores) / len(scores)

        # Normalize score to 0-1 range (assuming TF-IDF scores can be > 1)
        normalized_best = min(best_score, 1.0)
        normalized_avg = min(avg_score, 1.0)

        # Determine quality level
        if best_score >= 0.3:
            quality_level = "high"
            should_use_rag = True
            confidence_score = normalized_best
        elif best_score >= 0.15:
            quality_level = "medium"
            should_use_rag = True
            confidence_score = normalized_best * 0.8
        elif best_score >= self.min_threshold:
            quality_level = "low"
            should_use_rag = settings.rag_fallback_to_full_context
            confidence_score = normalized_best * 0.5
        else:
            quality_level = "insufficient"
            should_use_rag = False
            confidence_score = 0.0

        # Determine fallback strategy
        if quality_level == "none":
            fallback_strategy = "no_context"
        elif quality_level == "high" or quality_level == "medium":
            fallback_strategy = "use_rag"
        elif quality_level == "low":
            fallback_strategy = "use_with_warning"
        else:
            fallback_strategy = "no_rag"

        return {
            "quality_level": quality_level,
            "should_use_rag": should_use_rag,
            "fallback_strategy": fallback_strategy,
            "confidence_score": confidence_score,
            "best_score": best_score,
            "avg_score": avg_score,
            "total_results": len(results)
        }


def build_enhanced_prompt(
    query: str,
    results: List[dict],
    quality_info: dict
) -> tuple[str, str]:
    """
    Build enhanced prompt based on retrieval quality.

    Returns:
        tuple of (prompt, instruction_type)
    """
    if quality_info["quality_level"] == "none":
        # No context available
        return f"""Please answer the following query based on your general knowledge.
Since no relevant context was found in the conversation history, provide a helpful response.

Query: {query}

Answer:""", "general"

    elif quality_info["quality_level"] == "high":
        # High quality context
        context_parts = []
        for i, result in enumerate(results, 1):
            source = result.get('content', '')[:500]  # Truncate long content
            score_pct = result.get('score', 0) * 100
            context_parts.append(f"[Context {i}] (relevance: {score_pct:.1f}%):\n{source}")

        context_str = "\n\n".join(context_parts)

        return f"""Based on the following relevant context from the conversation history, please answer the query accurately.

Context:
{context_str}

Query: {query}

Answer:""", "high_quality"

    elif quality_info["quality_level"] == "medium":
        # Medium quality - use with context
        context_parts = []
        for i, result in enumerate(results, 1):
            source = result.get('content', '')[:400]
            score_pct = result.get('score', 0) * 100
            context_parts.append(f"[Context {i}] (relevance: {score_pct:.1f}%):\n{source}")

        context_str = "\n\n".join(context_parts)

        return f"""Based on the following context from the conversation history, please answer the query.
Note: Some context is provided but may not be directly relevant.

Context:
{context_str}

Query: {query}

Answer:""", "medium_quality"

    elif quality_info["quality_level"] == "low":
        # Low quality - warn model
        context_parts = []
        for i, result in enumerate(results[:3], 1):  # Only use top 3
            source = result.get('content', '')[:300]
            score_pct = result.get('score', 0) * 100
            context_parts.append(f"[Context {i}] (low relevance: {score_pct:.1f}%):\n{source}")

        context_str = "\n\n".join(context_parts)

        return f"""Warning: The following context has low relevance to the query. Please answer primarily based on your knowledge, and only use the context as supplementary reference.

Context:
{context_str}

Query: {query}

Answer:""", "low_quality"

    else:
        # Insufficient quality - no RAG
        return f"""Please answer the following query based on your general knowledge.
Note: No relevant context was found in the conversation history.

Query: {query}

Answer:""", "no_rag"


@router.post("/index", response_model=ChatHistoryIndexResponse)
async def index_chat_history(request: ChatHistoryIndexRequest):
    """
    Index chat history into vector store

    Features:
    - User-only indexing option (configurable)
    - Incremental indexing support
    - Stores both content and keywords for hybrid search
    """
    try:
        # Initialize services
        chunker = get_chunker(user_only=settings.rag_index_user_only)
        embedder = get_embedding_service()
        vector_store = get_vector_store()

        # Ensure collection exists
        vector_store.ensure_collection()

        # Convert messages to chunks
        messages = [msg.model_dump() for msg in request.messages]

        # Use incremental indexing if enabled
        indexed_ids = set()
        if settings.rag_incremental_index:
            # Get existing metadata to find already indexed messages
            # This is a simple approach - in production, you'd query the store
            pass

        chunks = chunker.chunk_conversation(messages, indexed_ids)

        if not chunks:
            return ChatHistoryIndexResponse(
                status="skipped",
                chat_id=request.chat_id,
                chunks_count=0,
                message="No new chunks to index"
            )

        # Generate embeddings
        contents = [chunk['content'] for chunk in chunks]
        vectors = embedder.encode(contents)

        # Store in vector store
        vector_store.upsert_chunks(chunks, vectors, request.chat_id)

        return ChatHistoryIndexResponse(
            status="success",
            chat_id=request.chat_id,
            chunks_count=len(chunks)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest):
    """
    Query with RAG enhancement

    Features:
    - Hybrid search (vector + keyword)
    - Quality-based fallback strategy
    - Detailed retrieval metadata
    """
    try:
        embedder = get_embedding_service()
        vector_store = get_vector_store()

        # Get query vector
        query_vector = embedder.encode(request.query)

        # Search with hybrid scoring (alpha controls vector vs keyword weight)
        alpha = settings.rag_hybrid_alpha

        results = vector_store.search(
            query_vector=query_vector[0],
            chat_id=request.chat_id,
            top_k=request.top_k,
            query_text=request.query,
            alpha=alpha
        )

        # Analyze retrieval quality
        analyzer = RetrievalQualityAnalyzer()
        quality_info = analyzer.analyze(results, request.query)

        # Build enhanced prompt based on quality
        enhanced_prompt, instruction_type = build_enhanced_prompt(
            request.query,
            results,
            quality_info
        )

        # Prepare response metadata
        response_contexts = None
        if request.include_context:
            response_contexts = [
                {
                    "id": r.get('id', ''),
                    "content": r.get('content', '')[:500],  # Truncate
                    "score": r.get('score', 0),
                    "vector_score": r.get('vector_score', r.get('score', 0)),
                    "keyword_score": r.get('keyword_score', 0),
                    "relevance": f"{r.get('score', 0) * 100:.1f}%"
                }
                for r in results
            ]

        return RAGQueryResponse(
            query=request.query,
            enhanced_prompt=enhanced_prompt,
            retrieved_contexts=response_contexts,
            context_count=len(results),
            quality_info={
                "level": quality_info["quality_level"],
                "confidence": quality_info["confidence_score"],
                "best_score": quality_info["best_score"],
                "should_use_rag": quality_info["should_use_rag"],
                "instruction_type": instruction_type
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/query-simple")
async def rag_query_simple(request: RAGQueryRequest):
    """
    Simple RAG query without quality metadata
    Returns only the enhanced prompt for compatibility
    """
    try:
        embedder = get_embedding_service()
        vector_store = get_vector_store()

        query_vector = embedder.encode(request.query)
        alpha = settings.rag_hybrid_alpha

        results = vector_store.search(
            query_vector=query_vector[0],
            chat_id=request.chat_id,
            top_k=request.top_k,
            query_text=request.query,
            alpha=alpha
        )

        # Simple context building
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[Context {i}]:\n{result['content']}")

        context_str = "\n\n".join(context_parts) if context_parts else ""

        enhanced_prompt = f"""Based on the following relevant context, please answer the query.

Context:
{context_str}

Query: {request.query}

Answer:"""

        return {
            "query": request.query,
            "enhanced_prompt": enhanced_prompt,
            "context_count": len(results)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/stats", response_model=RAGStatsResponse)
async def get_stats():
    """Get RAG system statistics"""
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()

        # Add configuration info
        stats["config"] = {
            "hybrid_alpha": settings.rag_hybrid_alpha,
            "min_threshold": settings.min_similarity_threshold,
            "fallback_enabled": settings.rag_fallback_to_full_context,
            "user_only_indexing": settings.rag_index_user_only,
            "incremental_indexing": settings.rag_incremental_index
        }

        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])

        return RAGStatsResponse(**stats)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")


@router.delete("/chat/{chat_id}")
async def delete_chat_index(chat_id: str):
    """Delete indexed chat history"""
    try:
        vector_store = get_vector_store()
        vector_store.delete_chat(chat_id)

        return {"status": "success", "chat_id": chat_id, "message": "Chat deleted"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

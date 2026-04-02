"""
Qdrant/Faiss vector store service with hybrid search support
Supports both Qdrant (remote) and Faiss (local)
"""
import os
from typing import List, Dict, Any, Optional, Set, Tuple
from core.config import get_settings

settings = get_settings()

# Check which vector store to use
USE_QDRANT = os.environ.get('USE_QDRANT', 'false').lower() == 'true'


class KeywordBM25:
    """
    Simple BM25 implementation for keyword-based retrieval.
    Used as fallback or complement to vector search.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: List[int] = []
        self.avgdl: float = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_term_freqs: List[Dict[str, int]] = []
        self._fitted = False

    def fit(self, texts: List[str]):
        """Fit BM25 on corpus"""
        import re
        from collections import Counter
        import math

        self.doc_lengths = []
        self.doc_freqs = Counter()
        self.doc_term_freqs = []

        for text in texts:
            # Tokenize
            text_lower = text.lower()
            chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', text_lower)
            english = re.findall(r'[a-zA-Z]{2,}', text_lower)
            terms = chinese + english

            # Term frequencies for this doc
            tf = Counter(terms)
            self.doc_term_freqs.append(tf)
            self.doc_lengths.append(sum(tf.values()))

            # Document frequencies
            for term in set(terms):
                self.doc_freqs[term] += 1

        # Calculate IDF
        n = len(texts)
        self.avgdl = sum(self.doc_lengths) / n if n > 0 else 1

        for term, df in self.doc_freqs.items():
            self.idf[term] = math.log((n - df + 0.5) / (df + 0.5) + 1)

        self._fitted = True

    def score(self, query: str, doc_idx: int) -> float:
        """Calculate BM25 score for query against document"""
        import re
        from collections import Counter

        if not self._fitted or doc_idx >= len(self.doc_term_freqs):
            return 0.0

        # Tokenize query
        text_lower = query.lower()
        chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', text_lower)
        english = re.findall(r'[a-zA-Z]{2,}', text_lower)
        query_terms = chinese + english

        score = 0.0
        tf = self.doc_term_freqs[doc_idx]
        dl = self.doc_lengths[doc_idx]

        for term in query_terms:
            if term not in self.idf:
                continue

            term_freq = tf.get(term, 0)
            idf = self.idf[term]

            # BM25 formula
            term_score = idf * (term_freq * (self.k1 + 1)) / \
                        (term_freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            score += term_score

        return score

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search BM25 index, return list of (doc_idx, score)"""
        if not self._fitted:
            return []

        scores = []
        for i in range(len(self.doc_term_freqs)):
            s = self.score(query, i)
            if s > 0:
                scores.append((i, s))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class VectorStore:
    """
    Vector store with hybrid search capabilities.
    Combines vector similarity with keyword matching.
    """

    def __init__(self):
        self.bm25: Optional[KeywordBM25] = None
        self.bm25_fitted = False

    def _extract_keywords_from_content(self, content: str) -> Set[str]:
        """Extract keywords from content for BM25"""
        import re
        from collections import Counter

        text_lower = content.lower()
        chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', text_lower)
        english = re.findall(r'[a-zA-Z]{2,}', text_lower)

        return set(chinese + english)


if USE_QDRANT:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse

    class VectorStore(VectorStore):
        """Qdrant vector store implementation with hybrid search"""

        _instance = None
        _client = None

        def __new__(cls):
            if cls._instance is None:
                instance = object.__new__(cls)
                # Initialize base class attributes
                instance.bm25 = None
                instance.bm25_fitted = False
                # Initialize Qdrant-specific attributes
                cls._instance = instance
            return cls._instance

        def connect(self):
            if self._client is None:
                self._client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port
                )
                print(f"Connected to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}")
            return self._client

        def get_client(self) -> QdrantClient:
            if self._client is None:
                return self.connect()
            return self._client

        def ensure_collection(self):
            client = self.get_client()
            try:
                client.get_collection(settings.qdrant_collection)
            except UnexpectedResponse:
                client.create_collection(
                    collection_name=settings.qdrant_collection,
                    vectors_config=models.VectorParams(
                        size=settings.vector_dimension,
                        distance=models.Distance.COSINE
                    )
                )

        def upsert_chunks(self, chunks, vectors, chat_id):
            client = self.get_client()
            points = []
            for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
                point_id = f"{chat_id}_{chunk.get('chunk_id', idx)}"
                content = chunk.get('content', '')
                keywords = self._extract_keywords_from_content(content)

                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "chat_id": chat_id,
                            "content": content,
                            "chunk_id": chunk.get('chunk_id', idx),
                            "metadata": chunk.get('metadata', {}),
                            "keywords": list(keywords),  # Store keywords for filtering
                        }
                    )
                )
            client.upsert(collection_name=settings.qdrant_collection, points=points)

        def search(
            self,
            query_vector,
            chat_id=None,
            top_k=None,
            query_text: str = None,
            alpha: float = None
        ):
            """
            Search with optional hybrid scoring.

            Args:
                query_vector: Query embedding vector
                chat_id: Filter by chat ID
                top_k: Number of results
                query_text: Query text for keyword boosting
                alpha: Weight for vector search (1-alpha for keyword)

            Returns:
                List of results with scores
            """
            client = self.get_client()
            k = top_k or settings.top_k
            alpha = alpha if alpha is not None else settings.rag_hybrid_alpha

            filter_condition = None
            if chat_id:
                filter_condition = models.Filter(
                    must=[models.FieldCondition(
                        key="chat_id",
                        match=models.MatchValue(value=chat_id)
                    )]
                )

            # Qdrant vector search
            results = client.query_points(
                collection_name=settings.qdrant_collection,
                query=query_vector,
                query_filter=filter_condition,
                limit=k * 2  # Get more results for hybrid scoring
            )

            if alpha >= 1.0:
                # Pure vector search
                return self._format_results(results.points, k)

            # Hybrid scoring with keywords
            hybrid_results = {}
            query_keywords = self._extract_keywords_from_content(query_text or "")

            for hit in results.points:
                base_score = hit.score

                # Keyword boost
                doc_keywords = set(hit.payload.get('keywords', []))
                keyword_match = len(query_keywords & doc_keywords) / max(len(query_keywords | doc_keywords), 1)

                # Combined score
                final_score = alpha * base_score + (1 - alpha) * keyword_match

                hybrid_results[hit.id] = {
                    "id": hit.id,
                    "vector_score": base_score,
                    "keyword_score": keyword_match,
                    "score": final_score,
                    "content": hit.payload.get('content', ''),
                    "metadata": hit.payload.get('metadata', {}),
                    "chat_id": hit.payload.get('chat_id', '')
                }

            # Sort by combined score and return top k
            sorted_results = sorted(hybrid_results.values(), key=lambda x: x['score'], reverse=True)
            return sorted_results[:k]

        def _format_results(self, points, k):
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "content": hit.payload.get('content', ''),
                    "metadata": hit.payload.get('metadata', {}),
                    "chat_id": hit.payload.get('chat_id', '')
                }
                for hit in points[:k]
            ]

        def delete_chat(self, chat_id):
            client = self.get_client()
            client.delete(
                collection_name=settings.qdrant_collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[models.FieldCondition(
                            key="chat_id",
                            match=models.MatchValue(value=chat_id)
                        )]
                    )
                )
            )

        def get_stats(self):
            client = self.get_client()
            try:
                info = client.get_collection(settings.qdrant_collection)
                return {
                    "collection": settings.qdrant_collection,
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "status": info.status
                }
            except Exception as e:
                return {"error": str(e)}

else:
    import faiss
    import numpy as np
    import json
    import os
    import threading

    class VectorStore(VectorStore):
        """Faiss local vector store implementation with hybrid search"""

        _instance = None
        _index = None
        _metadata = []
        _vectors: List[List[float]] = []  # Store vectors for BM25
        _lock = None
        _storage_dir = "./vector_store_data"

        def __new__(cls):
            if cls._instance is None:
                instance = object.__new__(cls)
                # Initialize base class attributes
                instance.bm25 = None
                instance.bm25_fitted = False
                # Initialize Faiss-specific attributes
                cls._instance = instance
                cls._lock = threading.Lock()
            return cls._instance

        def _ensure_storage(self):
            """Ensure storage directory exists"""
            os.makedirs(self._storage_dir, exist_ok=True)

        def connect(self):
            """Initialize Faiss index"""
            self._ensure_storage()
            index_path = os.path.join(self._storage_dir, "index.faiss")
            meta_path = os.path.join(self._storage_dir, "metadata.json")
            vectors_path = os.path.join(self._storage_dir, "vectors.json")

            if os.path.exists(index_path):
                self._index = faiss.read_index(index_path)
                with open(meta_path, 'r') as f:
                    self._metadata = json.load(f)
                try:
                    with open(vectors_path, 'r') as f:
                        self._vectors = json.load(f)
                except:
                    self._vectors = []
                print(f"Loaded Faiss index with {self._index.ntotal} vectors")
            else:
                self._index = faiss.IndexFlatIP(settings.vector_dimension)
                self._metadata = []
                self._vectors = []
                print("Created new Faiss index")

        def get_client(self):
            if self._index is None:
                self.connect()
            return self

        def ensure_collection(self):
            """Faiss doesn't need collection creation"""
            self.get_client()

        def upsert_chunks(self, chunks: List[Dict], vectors: List[List[float]], chat_id: str):
            with self._lock:
                self.get_client()

                # Store vectors for hybrid search
                self._vectors.extend(vectors)

                # Convert vectors to numpy array (normalize for cosine sim)
                vectors_np = np.array(vectors, dtype=np.float32)
                faiss.normalize_L2(vectors_np)

                # Add to index
                start_idx = self._index.ntotal
                self._index.add(vectors_np)

                # Store metadata
                for idx, chunk in enumerate(chunks):
                    chunk_id = f"{chat_id}_{chunk.get('chunk_id', idx)}"
                    keywords = self._extract_keywords_from_content(chunk.get('content', ''))
                    self._metadata.append({
                        "id": chunk_id,
                        "chat_id": chat_id,
                        "content": chunk.get('content', ''),
                        "chunk_id": chunk.get('chunk_id', idx),
                        "metadata": chunk.get('metadata', {}),
                        "keywords": list(keywords)
                    })

                # Save to disk
                self._save()
                print(f"Upserted {len(chunks)} chunks for chat_id: {chat_id}")

        def _save(self):
            """Save index and metadata to disk"""
            index_path = os.path.join(self._storage_dir, "index.faiss")
            meta_path = os.path.join(self._storage_dir, "metadata.json")
            vectors_path = os.path.join(self._storage_dir, "vectors.json")

            faiss.write_index(self._index, index_path)
            with open(meta_path, 'w') as f:
                json.dump(self._metadata, f)
            with open(vectors_path, 'w') as f:
                json.dump(self._vectors, f)

        def search(
            self,
            query_vector: List[float],
            chat_id: Optional[str] = None,
            top_k: int = None,
            query_text: str = None,
            alpha: float = None
        ) -> List[Dict]:
            """
            Search with optional hybrid scoring.

            Args:
                query_vector: Query embedding vector
                chat_id: Filter by chat ID
                top_k: Number of results
                query_text: Query text for keyword boosting
                alpha: Weight for vector search (1-alpha for keyword)

            Returns:
                List of results with scores
            """
            with self._lock:
                self.get_client()
                k = top_k or settings.top_k
                alpha = alpha if alpha is not None else settings.rag_hybrid_alpha

                # Handle empty index
                if self._index is None or self._index.ntotal == 0:
                    print("Faiss index is empty, returning empty results")
                    return []

                # Normalize query vector
                query_np = np.array([query_vector], dtype=np.float32)
                faiss.normalize_L2(query_np)

                # Search with more results for hybrid scoring
                search_k = min(k * 3, self._index.ntotal)
                if search_k <= 0:
                    search_k = 1
                scores, indices = self._index.search(query_np, search_k)

                # Get query keywords
                query_keywords = self._extract_keywords_from_content(query_text or "")

                # Calculate hybrid scores
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if idx < 0 or idx >= len(self._metadata):
                        continue

                    meta = self._metadata[idx]
                    if chat_id and meta.get('chat_id') != chat_id:
                        continue

                    vector_score = float(score)

                    # Keyword score
                    doc_keywords = set(meta.get('keywords', []))
                    keyword_score = len(query_keywords & doc_keywords) / max(len(query_keywords | doc_keywords), 1)

                    # Combined score
                    if alpha >= 1.0:
                        final_score = vector_score
                    elif alpha <= 0.0:
                        final_score = keyword_score
                    else:
                        final_score = alpha * vector_score + (1 - alpha) * keyword_score

                    results.append({
                        "id": meta['id'],
                        "vector_score": vector_score,
                        "keyword_score": keyword_score,
                        "score": final_score,
                        "content": meta.get('content', ''),
                        "metadata": meta.get('metadata', {}),
                        "chat_id": meta.get('chat_id', '')
                    })

                # Sort by combined score
                results.sort(key=lambda x: x['score'], reverse=True)

                return results[:k]

        def delete_chat(self, chat_id: str):
            with self._lock:
                self.get_client()

                # Find indices to remove
                remove_indices = []
                new_metadata = []
                new_vectors = []

                for idx, meta in enumerate(self._metadata):
                    if meta.get('chat_id') == chat_id:
                        remove_indices.append(idx)
                    else:
                        new_metadata.append(meta)
                        if idx < len(self._vectors):
                            new_vectors.append(self._vectors[idx])

                if not remove_indices:
                    return

                # Rebuild index
                self._metadata = new_metadata
                self._vectors = new_vectors

                if self._vectors:
                    vectors_np = np.array(self._vectors, dtype=np.float32)
                    faiss.normalize_L2(vectors_np)
                    self._index = faiss.IndexFlatIP(settings.vector_dimension)
                    self._index.add(vectors_np)
                else:
                    self._index = faiss.IndexFlatIP(settings.vector_dimension)

                self._save()
                print(f"Deleted chunks for chat_id: {chat_id}")

        def get_stats(self) -> Dict[str, Any]:
            self.get_client()
            return {
                "collection": "faiss_local",
                "vectors_count": self._index.ntotal if self._index else 0,
                "points_count": len(self._metadata),
                "status": "ready",
                "storage_dir": self._storage_dir,
                "hybrid_enabled": True,
                "alpha": settings.rag_hybrid_alpha
            }


def get_vector_store() -> VectorStore:
    return VectorStore()

"""
Embedding service for text vectorization
Local TF-IDF implementation for Chinese text - no external model download required
Supports hybrid search with keyword extraction
"""
from typing import List, Tuple, Union, Optional
from core.config import get_settings

settings = get_settings()


class KeywordExtractor:
    """
    Simple keyword extractor for hybrid search.
    Extracts Chinese and English keywords from text.
    """

    def __init__(self):
        self._stopwords = self._load_stopwords()

    def _load_stopwords(self) -> set:
        """Load Chinese and English stopwords"""
        chinese = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '上',
                   '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己',
                   '这', '他', '她', '它', '们', '这个', '那个', '什么', '怎么', '为什么', '可以',
                   '能', '吗', '呢', '吧', '啊', '哦', '嗯', '喂', '哈', '吗', '呢', '吧', '哦',
                   '呃', '唉', '哎', '呀', '哇', '哟', '嘿', '嗯', '唉', '哟', '喔'}
        english = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                   'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                   'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
                   'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through'}
        return chinese | english

    def extract(self, text: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Extract keywords with simple frequency-based importance.

        Args:
            text: Input text
            top_k: Number of top keywords to return

        Returns:
            List of (keyword, score) tuples
        """
        import re
        from collections import Counter

        text_lower = text.lower()
        keywords = []

        # Extract Chinese 2-4 character phrases
        chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', text_lower)
        for phrase in chinese:
            if phrase not in self._stopwords:
                keywords.append(phrase)

        # Extract English words
        english = re.findall(r'[a-zA-Z]{3,}', text_lower)
        for word in english:
            if word not in self._stopwords:
                keywords.append(word)

        # Count frequencies
        counter = Counter(keywords)

        # Return top-k with normalized scores
        if not counter:
            return []

        max_freq = counter.most_common(1)[0][1]
        results = []
        for word, count in counter.most_common(top_k):
            score = count / max_freq  # Normalize to 0-1
            results.append((word, score))

        return results

    def get_keyword_set(self, text: str, top_k: int = 10) -> set:
        """Get just the keyword set (for set operations)"""
        return {kw for kw, _ in self.extract(text, top_k)}


class EmbeddingService:
    """
    Local Chinese text embedding using TF-IDF with jieba tokenization.
    No network required - fully offline.
    """
    _instance = None
    _model = None
    _vectorizer = None
    _fitted = False
    _vector_dimension = 768
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load_model(self):
        """Load the local TF-IDF embedding model"""
        if self._model is None:
            print("Loading local Chinese TF-IDF embedding service...")
            self._model = self
            self._vector_dimension = settings.vector_dimension
            self.fit()
        return self._model
    
    def fit(self, texts=None):
        """Fit the TF-IDF vectorizer"""
        if self._fitted:
            return
        
        print("Fitting local TF-IDF vectorizer with character n-grams...")
        
        try:
            import jieba
            from sklearn.feature_extraction.text import TfidfVectorizer
            
            # Character-level tokenization for both English and Chinese
            def char_tokenize(text):
                # Convert to character list
                chars = list(text.lower())
                return chars
            
            # Character 2-grams and 3-grams for better matching
            def char_ngram_tokenize(text):
                text = text.lower()
                chars = list(text)
                tokens = []
                # Single characters
                tokens.extend(chars)
                # Bigrams
                for i in range(len(chars) - 1):
                    tokens.append(chars[i] + chars[i+1])
                # Trigrams
                for i in range(len(chars) - 2):
                    tokens.append(chars[i] + chars[i+1] + chars[i+2])
                return tokens
            
            self._vectorizer = TfidfVectorizer(
                analyzer='char',
                ngram_range=(1, 3),  # 1-3 character n-grams
                max_features=self._vector_dimension,
                min_df=1,
                max_df=1.0,
                sublinear_tf=True
            )
            
            # Fit with some sample texts
            sample_texts = [
                "hello hi hey",
                "天气 weather sun",
                "颜色 color blue purple",
                "喜欢 love prefer",
                "中文 chinese english",
                "你好 how are you",
                "蓝色 紫色 红色",
            ]
            
            self._vectorizer.fit(sample_texts)
            self._fitted = True
            print(f"TF-IDF vectorizer fitted with {len(self._vectorizer.vocabulary_)} features")
            
        except Exception as e:
            print(f"Failed to fit TF-IDF vectorizer: {e}")
            import traceback
            traceback.print_exc()
            self._vectorizer = None
            self._fitted = False
    
    def encode(self, texts):
        """
        Encode text(s) to vectors
        
        Args:
            texts: Single text or list of texts
            
        Returns:
            List of vectors (each vector is a list of floats)
        """
        self.load_model()
        
        if isinstance(texts, str):
            texts = [texts]
        
        if self._vectorizer is not None:
            try:
                vectors = self._vectorizer.transform(texts).toarray().tolist()
                # Ensure all vectors have the same dimension
                target_dim = self._vector_dimension
                result = []
                for v in vectors:
                    if len(v) < target_dim:
                        v = list(v) + [0.0] * (target_dim - len(v))
                    elif len(v) > target_dim:
                        v = v[:target_dim]
                    result.append(v)
                return result
            except Exception as e:
                print(f"TF-IDF encoding failed: {e}")
                return self._simple_encode(texts)
        else:
            return self._simple_encode(texts)
    
    def _simple_encode(self, texts):
        """Simple fallback encoding using character hashes"""
        import hashlib
        dim = self._vector_dimension
        
        vectors = []
        for text in texts:
            hash_digest = hashlib.sha256(text.encode()).digest()
            vector = []
            for i in range(dim):
                byte_idx = i % len(hash_digest)
                vector.append((hash_digest[byte_idx] / 255.0) * 2 - 1)
            vectors.append(vector)
        
        return vectors
    
    @property
    def dimension(self):
        return self._vector_dimension
    
    @property
    def is_loaded(self):
        return self._fitted

    def get_keywords(self, text: Union[str, List[str]], top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Extract keywords from text(s) for hybrid search boosting.

        Args:
            text: Single text or list of texts
            top_k: Number of keywords to extract per text

        Returns:
            List of (keyword, score) tuples
        """
        if not settings.rag_enable_boost_keywords:
            return []

        extractor = KeywordExtractor()

        if isinstance(text, str):
            return extractor.extract(text, top_k)
        else:
            all_keywords = []
            for t in text:
                all_keywords.extend(extractor.extract(t, top_k))
            return all_keywords

    def compute_keyword_score(self, query_keywords: set, context_keywords: set) -> float:
        """
        Compute keyword match score (Jaccard similarity).

        Args:
            query_keywords: Keywords from query
            context_keywords: Keywords from retrieved context

        Returns:
            Jaccard similarity score (0-1)
        """
        if not query_keywords or not context_keywords:
            return 0.0

        intersection = query_keywords & context_keywords
        union = query_keywords | context_keywords

        return len(intersection) / len(union) if union else 0.0

    def hybrid_encode(
        self,
        texts: Union[str, List[str]],
        boost_weight: float = 0.3
    ) -> Tuple[List[List[float]], List[List[Tuple[str, float]]]]:
        """
        Encode texts with keyword extraction for hybrid search.

        Args:
            texts: Single text or list of texts
            boost_weight: Weight for keyword-based boost (0-1)

        Returns:
            Tuple of (vectors, keywords) for hybrid search
        """
        # Get embeddings
        vectors = self.encode(texts)

        # Get keywords
        extractor = KeywordExtractor()

        if isinstance(texts, str):
            keywords = [extractor.extract(texts)]
        else:
            keywords = [extractor.extract(t) for t in texts]

        return vectors, keywords


def get_embedding_service():
    return EmbeddingService()

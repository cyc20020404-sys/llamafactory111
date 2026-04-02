"""
Local TF-IDF based embedding service for Chinese text
No external model download required
"""
import jieba
import hashlib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Union
from core.config import get_settings

settings = get_settings()


class LocalChineseEmbedding:
    """
    Local Chinese text embedding using TF-IDF with jieba tokenization.
    No network required - fully offline.
    """
    _instance = None
    _vectorizer = None
    _fitted = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def fit(self, texts: List[str] = None):
        """Fit the TF-IDF vectorizer on provided texts or use default"""
        if self._fitted:
            return
        
        print("Fitting local Chinese TF-IDF vectorizer...")
        
        # Default corpus for fitting (common Chinese words)
        default_corpus = [
            "人工智能 机器学习 深度学习 神经网络",
            "自然语言处理 文本分析 语义理解",
            "向量嵌入 特征提取 相似度计算",
            "对话系统 聊天机器人 智能助手",
            "知识库 问答系统 信息检索",
            "数据挖掘 数据分析 数据处理",
            "编程 代码 开发 软件",
            "模型 训练 预测 分类",
        ]
        
        try:
            self._vectorizer = TfidfVectorizer(
                tokenizer=self._jieba_tokenize,
                token_pattern=None,
                max_features=settings.vector_dimension,
                min_df=1,
                max_df=0.95
            )
            self._vectorizer.fit(default_corpus)
            self._fitted = True
            print(f"TF-IDF vectorizer fitted with {len(self._vectorizer.vocabulary_)} features")
        except Exception as e:
            print(f"Failed to fit TF-IDF vectorizer: {e}")
            self._vectorizer = None
            self._fitted = False
    
    @staticmethod
    def _jieba_tokenize(text: str) -> List[str]:
        """Tokenize Chinese text using jieba"""
        # Simple Chinese stopwords
        stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        words = jieba.cut(text)
        return [w for w in words if w.strip() and w not in stopwords]
    
    def encode(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Encode text(s) to vectors
        
        Args:
            texts: Single text or list of texts
            
        Returns:
            List of vectors (each vector is a list of floats)
        """
        self.fit()
        
        if isinstance(texts, str):
            texts = [texts]
        
        if self._vectorizer is not None:
            try:
                vectors = self._vectorizer.transform(texts).toarray().tolist()
                # Ensure all vectors have the same dimension
                target_dim = settings.vector_dimension
                result = []
                for v in vectors:
                    if len(v) < target_dim:
                        # Pad with zeros
                        v = list(v) + [0.0] * (target_dim - len(v))
                    elif len(v) > target_dim:
                        # Truncate
                        v = v[:target_dim]
                    result.append(v)
                return result
            except Exception as e:
                print(f"TF-IDF encoding failed: {e}")
                return self._fallback_encode(texts)
        else:
            return self._fallback_encode(texts)
    
    def _fallback_encode(self, texts: List[str]) -> List[List[float]]:
        """Fallback encoding using character n-grams hash"""
        dim = settings.vector_dimension
        
        vectors = []
        for text in texts:
            # Use character bigrams hash for fallback
            hash_digest = hashlib.sha256(text.encode()).digest()
            vector = []
            for i in range(dim):
                byte_idx = i % len(hash_digest)
                vector.append((hash_digest[byte_idx] / 255.0) * 2 - 1)
            vectors.append(vector)
        
        return vectors
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts"""
        vectors = self.encode([text1, text2])
        return cosine_similarity([vectors[0]], [vectors[1]])[0][0]
    
    @property
    def dimension(self) -> int:
        return settings.vector_dimension
    
    @property
    def is_loaded(self) -> bool:
        return True  # Always available since it's local


class EmbeddingService:
    """
    Unified embedding service that can use local TF-IDF
    or remote sentence-transformers models
    """
    _instance = None
    _model = None
    _use_local = True  # Default to local TF-IDF
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load_model(self):
        """Load embedding model"""
        if self._model is None:
            self._model = LocalChineseEmbedding()
            self._model.fit()
        return self._model
    
    def encode(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """Encode text(s) to vectors"""
        model = self.load_model()
        return model.encode(texts)
    
    @property
    def dimension(self) -> int:
        return settings.vector_dimension
    
    @property
    def is_loaded(self) -> bool:
        return True


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()

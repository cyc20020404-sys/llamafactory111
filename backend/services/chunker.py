"""
Text chunking service for RAG with improved strategies
"""
from typing import List, Dict, Any, Optional, Set
from core.config import get_settings

settings = get_settings()


class Chunker:
    """
    Chunks text into smaller pieces for embedding and retrieval.

    Features:
    - User-only indexing option (better retrieval quality)
    - Incremental indexing support (tracks indexed messages)
    - Conversation turn grouping
    - Clean content without format interference
    """

    def __init__(
        self,
        chunk_size: int = None,
        overlap: int = None,
        user_only: bool = None
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.overlap = overlap or settings.chunk_overlap
        self.user_only = user_only if user_only is not None else settings.rag_index_user_only

    def chunk_conversation(
        self,
        messages: List[Dict[str, Any]],
        indexed_message_ids: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk conversation messages into retrievable units.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            indexed_message_ids: Set of message IDs already indexed (for incremental indexing)

        Returns:
            List of chunk dicts with 'content', 'metadata', and 'chunk_id'
        """
        chunks = []
        indexed_message_ids = indexed_message_ids or set()

        # Filter messages based on strategy
        if self.user_only:
            # Only index user messages
            process_messages = [m for m in messages if m.get('role') == 'user']
        else:
            process_messages = messages

        # Build conversation context for each user message
        i = 0
        while i < len(process_messages):
            msg = process_messages[i]
            msg_id = msg.get('id', f'msg_{i}')

            # Skip already indexed messages (incremental indexing)
            if msg_id in indexed_message_ids:
                i += 1
                continue

            # Build context: user message + previous assistant reply (if any)
            chunk_content = msg.get('content', '')
            chunk_messages = [msg]

            # Find preceding assistant message for context
            if i > 0:
                prev_msg = process_messages[i - 1]
                if prev_msg.get('role') == 'assistant':
                    # Clean content without "[Assistant]:" prefix
                    assistant_content = prev_msg.get('content', '')
                    chunk_content = f"{assistant_content}\n\n{chunk_content}"
                    chunk_messages.insert(0, prev_msg)

            # Check chunk size and split if necessary
            if len(chunk_content) > self.chunk_size * 2:
                sub_chunks = self._split_long_chunk(chunk_content, chunk_messages)
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    'content': chunk_content,
                    'metadata': {
                        'message_ids': [m.get('id') for m in chunk_messages],
                        'roles': [m.get('role') for m in chunk_messages],
                        'timestamp': msg.get('timestamp'),
                        'indexed': False
                    }
                })

            i += 1

        # Add overlap between chunks
        chunks = self._add_overlap(chunks)

        # Add chunk IDs
        for idx, chunk in enumerate(chunks):
            chunk['chunk_id'] = idx

        return chunks

    def chunk_user_message_only(
        self,
        message: Dict[str, Any],
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a single chunk for a user message with optional context.

        Args:
            message: User message dict
            context: Optional assistant context to prepend

        Returns:
            Single chunk dict
        """
        content = message.get('content', '')

        if context:
            content = f"{context}\n\n{content}"

        # Truncate if too long
        if len(content) > self.chunk_size * 2:
            content = content[:self.chunk_size * 2]

        return {
            'content': content,
            'chunk_id': 0,
            'metadata': {
                'message_ids': [message.get('id')],
                'roles': [message.get('role')],
                'timestamp': message.get('timestamp'),
                'indexed': False,
                'has_context': bool(context)
            }
        }

    def _split_long_chunk(
        self,
        content: str,
        messages: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Split a long chunk into smaller pieces"""
        chunks = []
        chars_per_chunk = self.chunk_size

        # Split by sentence boundaries
        sentences = self._split_sentences(content)
        current_chunk = ''

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chars_per_chunk:
                current_chunk += '\n\n' + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append({
                        'content': current_chunk,
                        'metadata': {
                            'message_ids': [messages[0].get('id', 'unknown')],
                            'split': True
                        }
                    })
                current_chunk = sentence

        if current_chunk:
            chunks.append({
                'content': current_chunk,
                'metadata': {
                    'message_ids': [messages[0].get('id', 'unknown')],
                    'split': True
                }
            })

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        import re
        # Split by various sentence endings
        sentences = re.split(r'[。！？\n]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _add_overlap(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add overlap between consecutive chunks"""
        if len(chunks) <= 1 or self.overlap <= 0:
            return chunks

        overlapped_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0 and self.overlap > 0:
                prev_content = chunks[i - 1]['content']
                overlap_text = prev_content[-self.overlap:]
                chunk = {
                    'content': overlap_text + '\n\n' + chunk['content'],
                    'metadata': chunk['metadata']
                }
            overlapped_chunks.append(chunk)

        return overlapped_chunks

    def extract_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        Extract keywords from text for hybrid search boosting.

        Args:
            text: Input text
            top_k: Number of keywords to extract

        Returns:
            List of keywords
        """
        import re
        from collections import Counter

        # Simple keyword extraction: Chinese characters and English words
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        english_words = re.findall(r'[a-zA-Z]+', text)

        # Count frequencies (simple approach)
        keywords = []

        # Extract meaningful Chinese phrases (2-4 chars)
        for chars in chinese_chars:
            if len(chars) >= 2:
                for i in range(len(chars) - 1):
                    keywords.append(chars[i:i + 2])

        # English words
        keywords.extend([w.lower() for w in english_words if len(w) > 2])

        # Return top-k by frequency
        counter = Counter(keywords)
        return [k for k, _ in counter.most_common(top_k)]

    def get_indexed_ids_from_chunks(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Set[str]:
        """Extract message IDs from chunks for tracking"""
        indexed_ids = set()
        for chunk in chunks:
            msg_ids = chunk.get('metadata', {}).get('message_ids', [])
            indexed_ids.update(msg_ids)
        return indexed_ids


def get_chunker(user_only: bool = None) -> Chunker:
    return Chunker(user_only=user_only)

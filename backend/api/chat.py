"""
Chat API endpoints (forward to LLaMA Factory)
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import httpx

router = APIRouter()

# LLaMA Factory API configuration
LLAMA_API_URL = "http://localhost:8000"

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "qwen2.5-3b"
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True

class ChatResponse(BaseModel):
    response: str
    model: str
    usage: Optional[Dict[str, Any]] = None

@router.post("/completions")
async def chat_completions(request: ChatRequest):
    """
    Proxy chat completions to LLaMA Factory backend
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": request.model,
                "messages": [msg.model_dump() for msg in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": request.stream
            }
            
            response = await client.post(
                f"{LLAMA_API_URL}/v1/chat/completions",
                json=payload
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"LLaMA Factory error: {response.text}"
                )
            
            # Handle streaming responses
            if request.stream:
                from fastapi.responses import StreamingResponse
                return StreamingResponse(
                    response.aiter_text(),
                    media_type="text/event-stream"
                )
            else:
                return response.json()
    
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to LLaMA Factory backend. Please ensure it's running."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rag-completions")
async def rag_chat_completions(
    request: ChatRequest,
    use_rag: bool = True,
    rag_chat_id: Optional[str] = None
):
    """
    Chat completions with optional RAG enhancement
    """
    from api.rag import rag_query
    
    if use_rag:
        # Combine all messages into a query
        query = request.messages[-1].content if request.messages else ""
        
        # Get RAG context
        rag_request = RAGQueryRequest(
            query=query,
            chat_id=rag_chat_id,
            top_k=5,
            include_context=False
        )
        
        rag_response = await rag_query(rag_request)
        
        # Build messages with system prompt
        system_prompt = """You are a helpful AI assistant. Use the provided context to answer questions accurately. If the context doesn't contain relevant information, say so."""
        
        enhanced_messages = [
            {"role": "system", "content": system_prompt},
            *[msg.model_dump() for msg in request.messages[:-1]],
            {"role": "user", "content": rag_response.enhanced_prompt}
        ]
        
        request.messages = [ChatMessage(**msg) for msg in enhanced_messages]
    
    return await chat_completions(request)

# Import for rag_chat_completions
from models.schemas import RAGQueryRequest

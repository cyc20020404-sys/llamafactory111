"""
LLaMA Factory RAG Backend - FastAPI Application
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.rag import router as rag_router
from api.chat import router as chat_router
from core.config import settings

app = FastAPI(
    title="LLaMA Factory RAG API",
    description="RAG API for chat history knowledge retrieval",
    version="1.0.0"
)

# CORS 配置，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(rag_router, prefix="/api/rag", tags=["RAG"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])

@app.get("/")
async def root():
    return {"message": "LLaMA Factory RAG API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )

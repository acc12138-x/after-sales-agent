
from __future__ import annotations
from fastapi import APIRouter

from app.api.schemas.models import KnowledgeIngestRequest
from app.rag.chunking import chunk_document
from app.workflows.nodes.rag_search import get_retriever

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/ingest")
async def ingest(req: KnowledgeIngestRequest):
    chunks = chunk_document(
        req.content,
        doc_id=req.doc_id,
        source=req.source,
    )
    retriever = get_retriever()
    retriever.index_chunks(chunks)
    return {
        "doc_id": req.doc_id,
        "chunks": len(chunks),
        "total_in_collection": retriever.count(),
    }


@router.get("/stats")
async def stats():
    retriever = get_retriever()
    return {"total_chunks": retriever.count()}

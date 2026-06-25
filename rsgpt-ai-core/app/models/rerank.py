"""Reranker models for request/response"""

from typing import List

from pydantic import BaseModel, Field


class RerankDocument(BaseModel):
    """A document to be reranked"""

    text: str = Field(..., description="Document text content")
    index: int = Field(..., description="Original index of the document")


class RerankRequest(BaseModel):
    """Request model for reranking documents"""

    query: str = Field(..., min_length=1, description="Search query text")
    documents: List[str] = Field(
        ..., min_length=1, description="List of document texts to rerank"
    )
    top_k: int = Field(
        default=10, ge=1, le=100, description="Number of top results to return"
    )


class RerankResult(BaseModel):
    """A single reranked result"""

    text: str = Field(..., description="Document text")
    index: int = Field(..., description="Original index in input list")
    relevance_score: float = Field(
        ..., description="Relevance score from reranker (higher is better)"
    )


class RerankResponse(BaseModel):
    """Response model for reranking"""

    query: str = Field(..., description="Original query")
    results: List[RerankResult] = Field(..., description="Reranked documents")
    total_results: int = Field(..., description="Number of results returned")
    reranker_used: str = Field(
        ..., description="Which reranker was used (cohere or backup)"
    )

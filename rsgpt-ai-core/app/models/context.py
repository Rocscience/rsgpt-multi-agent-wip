"""Context retrieval models and data structures"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.channels import Channel, SourceChannel, UserPermission


class ContextItem(BaseModel):
    """A single context item retrieved from Pinecone"""

    id: str = Field(..., description="Unique identifier for the context item")
    text: str = Field(..., description="The retrieved text content")
    score: float = Field(..., description="Relevance score from vector similarity")
    channel: Optional[str] = Field(None, description="Channel this item came from")

    # Optional metadata fields based on the original OutputInfo structure
    url_link: Optional[str] = Field(None, description="URL link to source document")
    file_name: Optional[str] = Field(None, description="Source file name")
    software: Optional[str] = Field(None, description="Associated software")
    title: Optional[str] = Field(None, description="Document title")
    page_number: Optional[str] = Field(None, description="Page number in document")
    source: Optional[str] = Field(None, description="Source identifier")


class ContextRequest(BaseModel):
    """Request model for context retrieval"""

    query: str = Field(..., min_length=1, description="Search query text")

    # Source channels (ROC, DIANA, etc.) with conductor mapping
    source_channels: Optional[List[SourceChannel]] = Field(
        default=[SourceChannel.ROC],
        description="Source channels to search (e.g., ROC, DIANA, 3GSM, 2SI). Defaults to ['ROC']",
    )

    user_permission: UserPermission = Field(
        UserPermission.BASIC, description="User permission level"
    )
    top_k: Optional[int] = Field(
        None, ge=1, le=100, description="Number of results to return"
    )


class ContextResponse(BaseModel):
    """Response model for context retrieval"""

    query: str = Field(..., description="Original search query")
    results: List[ContextItem] = Field(..., description="Retrieved context items")
    channels_searched: List[Channel] = Field(
        ..., description="Channels that were searched"
    )
    total_results: int = Field(..., description="Total number of results returned")


class RawSearchResultItem(BaseModel):
    """A single result item from raw semantic search with flexible metadata"""

    id: str = Field(..., description="Unique identifier for the result")
    score: float = Field(..., description="Relevance score from vector similarity")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw metadata from Pinecone (structure unknown)",
    )


class RawSemanticSearchRequest(BaseModel):
    """Request model for raw semantic search without channel mapping"""

    query: str = Field(..., min_length=1, description="Search query text")
    namespace: str = Field(..., description="Pinecone namespace to search in")
    index_name: str = Field(..., description="Pinecone index name")
    top_k: int = Field(
        default=10, ge=1, le=100, description="Number of results to return"
    )


class RawSemanticSearchResponse(BaseModel):
    """Response model for raw semantic search"""

    query: str = Field(..., description="Original search query")
    results: List[RawSearchResultItem] = Field(
        ..., description="Retrieved results with raw metadata"
    )
    namespace: str = Field(..., description="Namespace that was searched")
    index_name: str = Field(..., description="Index that was searched")
    total_results: int = Field(..., description="Total number of results returned")


class SearchResultSource(BaseModel):
    """Source information for a search result context"""

    title: Optional[str] = Field(None, description="Document title")
    url: Optional[str] = Field(None, description="URL to the source document")
    file_name: Optional[str] = Field(None, description="Source file name")
    page: Optional[int] = Field(None, description="Page number in the document")


class SearchResultContext(BaseModel):
    """A single context item in search knowledge results"""

    text: str = Field(..., description="The context text content")
    score: float = Field(..., description="Relevance score from vector search")
    rerank_score: float = Field(..., description="Score after reranking")
    rank: int = Field(..., ge=1, description="Rank position in results (1-indexed)")
    channel: Optional[str] = Field(None, description="Channel this context came from")
    source: SearchResultSource = Field(..., description="Source metadata")


class SearchResultMetadata(BaseModel):
    """Metadata about the search operation"""

    total_retrieved: int = Field(..., description="Total number of results retrieved")
    channels_searched: List[str] = Field(
        ..., description="List of channels that were searched"
    )
    reranker_used: Optional[str] = Field(None, description="Reranker model used")
    results_returned: int = Field(
        ..., description="Number of results actually returned"
    )


class SearchKnowledgeResult(BaseModel):
    """Result from search_knowledge agent tool"""

    query: str = Field(..., description="The original search query")
    contexts: List[SearchResultContext] = Field(
        ..., description="List of context results with metadata"
    )
    metadata: SearchResultMetadata = Field(
        ..., description="Metadata about the search operation"
    )

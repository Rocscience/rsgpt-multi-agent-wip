"""Services package for core business logic"""

from .auth import AuthService, auth_service, get_auth_service
from .config import (
    ConductorService,
    ConfigService,
    get_conductor_service,
    get_config_service,
)
from .reranker import (
    CohereReranker,
    KeepTopKReranker,
    RerankerService,
    get_cohere_reranker,
    get_keep_topk_reranker,
    get_reranker_service,
)
from .search import (
    ContextService,
    EmbeddingService,
    PineconeService,
    get_context_service,
    get_embedding_service,
    get_pinecone_service,
)
from .streaming import StreamingService, connection_manager, streaming_service

__all__ = [
    # Auth services
    "AuthService",
    "auth_service",
    "get_auth_service",
    # Config services
    "ConductorService",
    "get_conductor_service",
    "ConfigService",
    "get_config_service",
    # Reranker services
    "CohereReranker",
    "KeepTopKReranker",
    "RerankerService",
    "get_cohere_reranker",
    "get_keep_topk_reranker",
    "get_reranker_service",
    # Search services
    "ContextService",
    "get_context_service",
    "EmbeddingService",
    "get_embedding_service",
    "PineconeService",
    "get_pinecone_service",
    # Streaming services
    "StreamingService",
    "streaming_service",
    "connection_manager",
]

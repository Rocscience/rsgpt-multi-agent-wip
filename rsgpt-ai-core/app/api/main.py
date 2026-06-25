import logging

from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse

from app.api.routes import (
    agent,
    chat,
    config,
    context,
    health,
    rerank,
    search,
    websocket,
)
from app.config import settings

logger = logging.getLogger(__name__)

api_app = FastAPI(
    title="RSGPT AI Core API",
    description="API for RSGPT AI Core Service",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)


@api_app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc):
    logger.error(f"Response validation error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal data formatting error",
            "detail": "Response format is invalid",
        },
    )


# Add health routes
api_app.include_router(health.health_router, prefix="/health", tags=["health"])
api_app.include_router(chat.chat_router, prefix="/chat", tags=["chat"])
api_app.include_router(agent.agent_router, prefix="/agent", tags=["agent"])
api_app.include_router(context.context_router, prefix="/context", tags=["context"])
api_app.include_router(config.config_router, prefix="/config", tags=["config"])
api_app.include_router(rerank.rerank_router, prefix="/rerank", tags=["rerank"])
api_app.include_router(search.search_router, tags=["search"])
api_app.include_router(websocket.websocket_router, prefix="/ws", tags=["websocket"])

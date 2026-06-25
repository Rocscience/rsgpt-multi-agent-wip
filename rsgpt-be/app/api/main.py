import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse
from app.api.routes import chat, user, health, quota, device, mcp_registry, rslog, auth, desktop, admin
from app.config import settings

logger = logging.getLogger(__name__)

api_app = FastAPI(
    title="RSGPT API",
    description="API for RSGPT",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

# CORS middleware must be added to mounted sub-applications
# The parent app's CORS middleware does not apply to mounted apps
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

@api_app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc):
    logger.error(f"Response validation error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal data formatting error", "detail": "Response format is invalid"}
    )

# Add all routes
api_app.include_router(health.router)  # Health endpoints don't need auth
api_app.include_router(auth.router, tags=["Authentication"])  # New auth endpoints
api_app.include_router(user.user_router, prefix="/user", tags=["user"])
api_app.include_router(chat.chat_router, prefix="/chat", tags=["chat"])
api_app.include_router(quota.router, prefix="/quota", tags=["quota"])
api_app.include_router(device.device_router, prefix="/device", tags=["device"])
api_app.include_router(mcp_registry.router, tags=["MCP Registry"])
api_app.include_router(desktop.router, tags=["Desktop"])
api_app.include_router(rslog.rslog_router, prefix="/rslog", tags=["RSLog"])
api_app.include_router(admin.admin_router, prefix="/admin", tags=["Admin"])
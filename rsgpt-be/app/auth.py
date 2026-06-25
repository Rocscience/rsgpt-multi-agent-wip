from fastapi_plugin import Auth0FastAPI
from app.config import settings

auth0 = Auth0FastAPI(
    domain=settings.auth0_domain,
    audience=settings.auth0_audience
)

from fastapi import FastAPI

from middleware.request_logging import RequestLoggingMiddleware
from routers import agent, auth, google_accounts


def create_app() -> FastAPI:
    app = FastAPI(title="Noon Backend", version="0.1.0")

    # Add request logging middleware
    app.add_middleware(
        RequestLoggingMiddleware,
        exclude_paths=["/healthz", "/docs", "/openapi.json", "/redoc"],
    )

    app.include_router(auth.router)
    app.include_router(google_accounts.router)
    app.include_router(agent.router)

    @app.get("/healthz", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app

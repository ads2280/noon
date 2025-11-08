from fastapi import FastAPI

from routers import auth, google_accounts


def create_app() -> FastAPI:
    app = FastAPI(title="Noon Backend", version="0.1.0")

    app.include_router(auth.router)
    app.include_router(google_accounts.router)

    @app.get("/healthz", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


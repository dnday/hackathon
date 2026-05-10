from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.cron import router as cron_router
from app.api.v1.validation import router as validation_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.firebase_init import initialize_firebase


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(validation_router, prefix=settings.api_v1_prefix)
    app.include_router(cron_router, prefix=settings.api_v1_prefix)

    @app.on_event("startup")
    async def on_startup() -> None:
        initialize_firebase()

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

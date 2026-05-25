from __future__ import annotations
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.cron import router as cron_router
from app.api.v1.validation import router as validation_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.firebase_init import initialize_firebase


from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="1.0.0", docs_url=None, redoc_url=None)

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=app.title + " - ReDoc",
            redoc_js_url="https://unpkg.com/redoc@next/bundles/redoc.standalone.js",
        )

    @app.middleware("http")
    async def redirect_ip_to_nip_io(request: Request, call_next):
        host = request.headers.get("host", "")
        # Jika akses menggunakan IP mentah, alihkan ke nip.io tanpa port dan paksa HTTPS
        if "103.27.207.136" in host and "nip.io" not in host:
            new_url = f"https://103.27.207.136.nip.io{request.url.path}"
            if request.url.query:
                new_url += f"?{request.url.query}"
            return RedirectResponse(url=new_url, status_code=307)
        return await call_next(request)

    @app.get("/", include_in_schema=False)
    async def root():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not Authorized")

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

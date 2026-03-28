from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import (
    OpslyException,
    generic_exception_handler,
    http_exception_handler,
    opsly_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import RequestIDMiddleware

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("opsly")


def create_app() -> FastAPI:
    """FastAPI application factory."""

    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version="1.0.0",
        description=(
            "Field Operations ERP for Rahul Electricals & Creative Solutions.\n\n"
            "## Authentication\n"
            "Click **Authorize 🔒** (top-right), enter your **email** as username and **password**, "
            "then click Authorize. All endpoints will be authenticated automatically.\n\n"
            "Alternatively: call `POST /api/v1/auth/login`, copy the `access_token`, "
            "and paste it into the BearerAuth section as `Bearer <token>`."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "defaultModelsExpandDepth": -1,
        },
        openapi_tags=[
            {"name": "Auth",              "description": "Login, logout, token refresh"},
            {"name": "Users",             "description": "User management"},
            {"name": "Tickets",           "description": "Job / service tickets"},
            {"name": "Attendance",        "description": "Engineer attendance"},
            {"name": "Inventory",         "description": "Parts & inventory items and stock management"},
            {"name": "Inventory Categories", "description": "Inventory category management"},
            {"name": "Low Stock Config",  "description": "Per-item low-stock threshold overrides"},
            {"name": "Tenders",           "description": "Tender management"},
            {"name": "Expenses",          "description": "Expense claims"},
            {"name": "Uploads",           "description": "File uploads (MinIO)"},
            {"name": "Dashboard",         "description": "Summary statistics"},
            {"name": "Client Portal",     "description": "Client-facing endpoints"},
            {"name": "Sync",              "description": "Offline sync"},
            {"name": "Health",            "description": "Health check"},
            {"name": "Bulk Import",       "description": "Bulk staff & inventory import"},
            {"name": "Payroll",           "description": "Salary records & advance payments"},
        ],
    )

    # ── OpenAPI security scheme (Bearer JWT + OAuth2 password flow for Swagger UI) ─
    from fastapi.openapi.utils import get_openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        schema.setdefault("components", {}).setdefault("securitySchemes", {})

        # BearerAuth — lets users paste a raw token via the 🔒 Authorize dialog
        schema["components"]["securitySchemes"]["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste the `access_token` returned by POST /auth/login",
        }

        # OAuth2PasswordBearer — gives Swagger UI a proper username/password form
        # in the Authorize dialog that calls /auth/login and captures the token.
        schema["components"]["securitySchemes"]["OAuth2PasswordBearer"] = {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "/api/v1/auth/login",
                    "scopes": {},
                }
            },
            "description": "Log in with email (username) and password directly from Swagger UI",
        }

        # Apply both schemes globally to every protected operation
        for path, path_item in schema.get("paths", {}).items():
            if path in ("/api/v1/auth/login", "/api/v1/auth/refresh", "/health"):
                continue
            for operation in path_item.values():
                if isinstance(operation, dict):
                    operation.setdefault("security", [
                        {"BearerAuth": []},
                        {"OAuth2PasswordBearer": []},
                    ])
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

    # ── Middleware ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # ── Rate limiting (SlowAPI) ─────────────────────────────────────────────────
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded

    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Exception handlers ──────────────────────────────────────────────────────
    app.add_exception_handler(OpslyException, opsly_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # ── Routers ─────────────────────────────────────────────────────────────────
    from app.routers import (
        auth,
        users,
        tickets,
        attendance,
        inventory,
        tenders,
        expenses,
        uploads,
        dashboard,
        client_portal,
        sync,
        bulk_import,
        payroll,
    )

    PREFIX = "/api/v1"
    app.include_router(auth.router, prefix=PREFIX)
    app.include_router(users.router, prefix=PREFIX)
    app.include_router(tickets.router, prefix=PREFIX)
    app.include_router(attendance.router, prefix=PREFIX)
    app.include_router(inventory.router, prefix=PREFIX)
    app.include_router(tenders.router, prefix=PREFIX)
    app.include_router(expenses.router, prefix=PREFIX)
    app.include_router(uploads.router, prefix=PREFIX)
    app.include_router(dashboard.router, prefix=PREFIX)
    app.include_router(client_portal.router, prefix=PREFIX)
    app.include_router(sync.router, prefix=PREFIX)
    app.include_router(bulk_import.router, prefix=PREFIX)
    app.include_router(payroll.router, prefix=PREFIX)

    # ── Startup / Shutdown events ───────────────────────────────────────────────
    @app.on_event("startup")
    async def _startup() -> None:
        logger.info("Starting %s API...", settings.APP_NAME)

        # Register SQLAlchemy audit listeners
        from app.db.audit import register_audit_listeners
        register_audit_listeners()

        # Start background scheduler
        from app.tasks.scheduler import start_scheduler
        start_scheduler()

        # Verify Redis connectivity
        try:
            from app.utils.idempotency import get_redis
            get_redis().ping()
            logger.info("Redis connection: OK")
        except Exception as exc:
            logger.warning("Redis not available: %s", exc)

        logger.info("%s API started successfully.", settings.APP_NAME)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        from app.tasks.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("%s API shut down.", settings.APP_NAME)

    # ── Health check ────────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health_check():
        """
        Health check endpoint.
        Returns status of the API, database, and Redis connections.
        """
        from app.db.base import engine
        db_status = "ok"
        try:
            with engine.connect() as conn:
                conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        except Exception:
            db_status = "error"

        redis_status = "ok"
        try:
            from app.utils.idempotency import get_redis
            get_redis().ping()
        except Exception:
            redis_status = "error"

        return {"status": "ok", "db": db_status, "redis": redis_status}

    return app


app = create_app()

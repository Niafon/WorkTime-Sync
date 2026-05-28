import logging

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import AsyncSessionLocal


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count"],
    )

    @app.get("/health", tags=["health"])
    async def health_check() -> JSONResponse:
        # Подтверждаем не только что процесс жив, но и что БД отвечает —
        # иначе load-balancer держит трафик на инстансе с мёртвым postgres.
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logging.getLogger(__name__).warning("health: database check failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "degraded", "database": "down"},
            )
        return JSONResponse(content={"status": "ok", "database": "up"})

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()

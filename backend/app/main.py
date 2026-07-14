from pathlib import Path
from time import perf_counter

from logging.config import dictConfig

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

REQUEST_TRACE_LOG_PATH = Path(__file__).resolve().parents[2] / "request_trace.log"


def configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "app": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False,
                }
            },
        }
    )


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="AI Interview v2 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def trace_requests(request: Request, call_next):
        started_at = perf_counter()
        response = await call_next(request)
        elapsed_ms = (perf_counter() - started_at) * 1000
        message = (
            f"{request.method} {request.url.path} "
            f"status={response.status_code} elapsed_ms={elapsed_ms:.1f}"
        )
        print(message, flush=True)
        try:
            with REQUEST_TRACE_LOG_PATH.open("a", encoding="utf-8") as trace_file:
                trace_file.write(f"{message}\n")
        except OSError:
            pass
        return response

    @app.get("/health", tags=["health"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()

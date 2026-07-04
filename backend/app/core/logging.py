"""
Structured logging configuration using structlog.
Call configure_logging() once at app startup.
"""

import logging
import sys

import structlog
from app.core.config import settings


from typing import Any

def configure_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    def safe_add_logger_name(logger: Any, method_name: str, event_dict: Any) -> Any:
        if hasattr(logger, "name"):
            event_dict["logger"] = logger.name
        else:
            event_dict["logger"] = "root"
        return event_dict

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        safe_add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any
    if settings.DEBUG:
        # Human-friendly coloured output in development
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # Machine-parseable JSON in production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libs emit structured logs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.DEBUG else logging.WARNING
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # avoid double-logging

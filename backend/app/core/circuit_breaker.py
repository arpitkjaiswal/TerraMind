"""
Circuit breaker + exponential backoff utilities.

Circuit breaker:
  - Wraps LLM provider calls (Cognee's cognify/search steps)
  - States: CLOSED → OPEN (after N failures) → HALF_OPEN (after recovery timeout)
  - When OPEN: returns a clear "temporarily unavailable" error instead of degraded answer

Exponential backoff:
  - Wraps ingestion jobs (document parsing, OCR, S3 upload)
  - Max 5 retries, exponential wait with jitter
"""

from __future__ import annotations
from functools import wraps
from typing import Callable, Any

import structlog
import pybreaker
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from fastapi import HTTPException, status
import logging

log = structlog.get_logger(__name__)
_stdlib_log = logging.getLogger(__name__)

# ── Circuit Breaker ────────────────────────────────────────────────────────────

class AegisCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        log.warning(
            "circuit_breaker.state_change",
            breaker=cb.name,
            old=old_state.name,
            new=new_state.name,
        )

    def failure(self, cb, exc):
        log.error("circuit_breaker.failure", breaker=cb.name, error=str(exc))

    def success(self, cb):
        log.info("circuit_breaker.success", breaker=cb.name)


_llm_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=60,
    name="llm_provider",
    listeners=[AegisCircuitBreakerListener()],
)


from datetime import datetime, timedelta, timezone

def llm_circuit_breaker(fn: Callable) -> Callable:
    """
    Decorator: wraps async LLM-calling functions with a circuit breaker.
    When open, raises HTTP 503 with a clear 'temporarily unavailable' message.
    """
    @wraps(fn)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            with _llm_breaker._lock:
                state = _llm_breaker.state
                if state.name == "open":
                    timeout = timedelta(seconds=_llm_breaker.reset_timeout)
                    opened_at = _llm_breaker._state_storage.opened_at
                    now = datetime.now(timezone.utc) if opened_at and opened_at.tzinfo else datetime.now()
                    if opened_at and now < opened_at + timeout:
                        raise pybreaker.CircuitBreakerError("Circuit still open")
                    _llm_breaker.half_open()

                # Notify listeners before call
                for listener in _llm_breaker.listeners:
                    listener.before_call(_llm_breaker, fn, *args, **kwargs)
        except pybreaker.CircuitBreakerError:
            log.error("circuit_breaker.open", function=fn.__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "llm_unavailable",
                    "message": (
                        "The AI reasoning service is temporarily unavailable. "
                        "Your query has been logged and will be retried automatically. "
                        "Please try again in a few minutes."
                    ),
                },
            )

        try:
            ret = await fn(*args, **kwargs)
        except BaseException as e:
            with _llm_breaker._lock:
                if _llm_breaker.is_system_error(e):
                    _llm_breaker.state._handle_error(e, reraise=False)
                else:
                    _llm_breaker.state._handle_success()
            raise
        else:
            with _llm_breaker._lock:
                _llm_breaker.state._handle_success()
            return ret

    return wrapper


# ── Exponential backoff for ingestion jobs ────────────────────────────────────

ingestion_retry = retry(
    retry=retry_if_exception_type((IOError, TimeoutError, ConnectionError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)

ocr_retry = retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_random_exponential(min=1, max=10),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)

llm_retry = retry(
    retry=retry_if_exception_type(Exception),
    wait=wait_exponential(multiplier=2, min=3, max=60),
    stop=stop_after_attempt(4),
    before_sleep=before_sleep_log(_stdlib_log, logging.WARNING),
    reraise=True,
)

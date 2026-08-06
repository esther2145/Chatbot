"""Optional, failure-isolated Langfuse observability for chat requests."""

import logging
from typing import Any

from .config import settings

logger = logging.getLogger(__name__)

_client = None

if settings.langfuse_public_key and settings.langfuse_secret_key:
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
            environment=settings.langfuse_environment,
        )
        logger.info("Langfuse monitoring enabled")
    except Exception:  # noqa: BLE001
        logger.exception("Langfuse monitoring disabled because initialization failed")


def monitoring_enabled() -> bool:
    return _client is not None


def trace_chat(
    session_id: str,
    question: str,
    answer: str,
    citations: list[Any],
    *,
    channel: str = "text",
    latency_ms: int | None = None,
) -> None:
    """Record one completed turn. Monitoring failures never affect the response."""
    if not _client:
        return

    try:
        from langfuse import propagate_attributes

        metadata = {
            "channel": channel,
            "citation_count": len(citations),
            "answer_characters": len(answer),
        }
        if latency_ms is not None:
            metadata["latency_ms"] = latency_ms

        with propagate_attributes(
            trace_name="nssf-chat",
            session_id=session_id,
            metadata={"channel": channel},
        ):
            with _client.start_as_current_observation(
                as_type="chain",
                name="nssf-chat-turn",
                input={"question": question},
                output={"answer": answer, "citations": citations},
                metadata=metadata,
            ):
                pass
    except Exception:  # noqa: BLE001
        logger.exception("Langfuse chat trace failed")


def trace_feedback(session_id: str, message: str, rating: str) -> None:
    """Attach user feedback to the Langfuse conversation session."""
    if not _client:
        return

    try:
        _client.create_score(
            name="user-feedback",
            value=rating == "up",
            data_type="BOOLEAN",
            comment=message,
            session_id=session_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Langfuse feedback trace failed")


def shutdown_monitoring() -> None:
    """Flush queued telemetry during an orderly server shutdown."""
    if not _client:
        return
    try:
        _client.shutdown()
    except Exception:  # noqa: BLE001
        logger.exception("Langfuse shutdown failed")

"""
Optional Langfuse monitoring. Fully defensive: if keys aren't set or the SDK
isn't happy, the app keeps working and simply skips tracing.
"""
from .config import settings

_lf = None
if settings.langfuse_public_key and settings.langfuse_secret_key:
    try:
        from langfuse import Langfuse

        _lf = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[monitoring] Langfuse disabled: {exc}")


def trace_chat(session_id, question, answer, citations):
    if not _lf:
        return
    try:
        _lf.trace(
            name="nssf-chat",
            session_id=session_id,
            input=question,
            output=answer,
            metadata={"citations": citations},
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[monitoring] trace failed: {exc}")


def trace_feedback(session_id, message, rating):
    if not _lf:
        return
    try:
        _lf.score(name="user-feedback", value=1 if rating == "up" else 0,
                  comment=message, trace_id=session_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[monitoring] feedback failed: {exc}")

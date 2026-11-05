"""JSON logging for the whole process (structlog + standard library, e.g. uvicorn).

Privacy: never log `device_id`, driver codes or accessibility needs tied to an identifier.

Exceptions (H-01, realtime_events AC-12): no log line carries the message or the traceback of an
exception, because either may contain an identifier. A record with exception information keeps
only the exception type, as `error_type`:

- structlog events (`log.exception(...)`, `exc_info=...`) keep their event and fields;
- standard library records (uvicorn's "Exception in ASGI application", asyncio…) become the event
  `unhandled_exception`, since their message may be built from the exception too.

Two layers do it: a structlog processor (structlog events and the formatter of foreign records)
and a `logging.Filter` on the root handler, so the rule holds whatever the formatter does.
"""

import logging
import sys

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

UNHANDLED_EXCEPTION = "unhandled_exception"
_EXCEPTION_KEYS = ("exc_info", "exception", "exc_text", "stack_info", "stack")
_ERROR_TYPE_ATTR = "avisabus_error_type"


def _error_type(exc_info: object) -> str | None:
    """Name of the exception type described by any accepted form of `exc_info`."""
    if isinstance(exc_info, BaseException):
        return type(exc_info).__name__
    if isinstance(exc_info, tuple):
        exc_type = exc_info[0] if exc_info else None
        return exc_type.__name__ if isinstance(exc_type, type) else None
    if exc_info:
        current = sys.exc_info()[0]
        return current.__name__ if current is not None else None
    return None


def drop_exception_details(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    """structlog processor: replace exception information by `error_type` (AC-12)."""
    record = event_dict.get("_record")
    sanitised_type = getattr(record, _ERROR_TYPE_ATTR, None) if record is not None else None
    if sanitised_type is not None:  # already rewritten by `ExceptionDetailsFilter`
        event_dict.setdefault("error_type", sanitised_type)
    exc_info = event_dict.get("exc_info")
    if not exc_info and "exception" not in event_dict and "exc_text" not in event_dict:
        event_dict.pop("exc_info", None)  # `exc_info=False`
        return event_dict
    error_type = _error_type(exc_info)
    for key in _EXCEPTION_KEYS:
        event_dict.pop(key, None)
    if error_type is not None:
        event_dict.setdefault("error_type", error_type)
    if event_dict.get("_from_structlog") is False:
        event_dict["event"] = UNHANDLED_EXCEPTION
    return event_dict


class ExceptionDetailsFilter(logging.Filter):
    """Handler filter: a standard library record with exception information is replaced by a
    copy without message, arguments, traceback nor stack (AC-12). structlog records are left to
    `drop_exception_details`."""

    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        if isinstance(record.msg, dict) or not (
            record.exc_info or record.exc_text or getattr(record, _ERROR_TYPE_ATTR, None)
        ):
            return True
        error_type = _error_type(record.exc_info) or getattr(record, _ERROR_TYPE_ATTR, None)
        clean = logging.makeLogRecord(record.__dict__)
        clean.msg = UNHANDLED_EXCEPTION
        clean.args = ()
        clean.exc_info = None
        clean.exc_text = None
        clean.stack_info = None
        setattr(clean, _ERROR_TYPE_ATTR, error_type or "Exception")
        return clean


def configure_logging(level: str = "INFO") -> None:
    """Emit every log event as one JSON line with timestamp, level, event and logger."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        drop_exception_details,
    ]
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            drop_exception_details,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(ExceptionDetailsFilter())

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())

    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

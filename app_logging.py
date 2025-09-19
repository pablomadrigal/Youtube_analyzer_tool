"""
Logging configuration with request correlation.
"""
import logging
import sys
from typing import Any, Dict
from contextvars import ContextVar
import uuid

# Context variable for request correlation
request_id_var: ContextVar[str] = ContextVar('request_id', default='')


class RequestCorrelationFilter(logging.Filter):
    """Filter to add request ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get('')
        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging configuration."""
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestCorrelationFilter())
    
    root_logger.addHandler(console_handler)


def set_request_id(request_id: str = None) -> str:
    """Set request ID for correlation."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_var.set(request_id)
    return request_id


def get_request_id() -> str:
    """Get current request ID."""
    return request_id_var.get('')


def log_with_context(level: str, message: str, **kwargs: Any) -> None:
    """Log message with request context."""
    logger = logging.getLogger(__name__)
    getattr(logger, level.lower())(message, extra=kwargs)


def redact_secrets(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive information from logs."""
    redacted = data.copy()
    secret_keys = ['api_key', 'password', 'secret', 'token']
    
    for key, value in redacted.items():
        if any(secret in key.lower() for secret in secret_keys):
            redacted[key] = '***REDACTED***'
        elif isinstance(value, dict):
            redacted[key] = redact_secrets(value)
    
    return redacted

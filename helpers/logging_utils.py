# -*- coding: utf-8 -*-
"""
Structured logging utilities for ShuttleBee
Provides JSON-formatted logging for better log aggregation and monitoring
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps

_logger = logging.getLogger(__name__)


class StructuredLogger:
    """Structured logging helper with JSON output"""

    def __init__(self, name: str):
        """
        Initialize structured logger

        Args:
            name: Logger name (typically module name)
        """
        self.logger = logging.getLogger(name)
        self.name = name

    def _format_structured_message(
        self,
        event: str,
        level: str,
        **context
    ) -> str:
        """
        Format message as JSON structure

        Args:
            event: Event name/type
            level: Log level
            **context: Additional context fields

        Returns:
            str: JSON-formatted log message
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'logger': self.name,
            'level': level,
            'event': event,
            **context
        }

        return json.dumps(log_data, default=str)

    def debug(self, event: str, **context):
        """Log debug message with structured data"""
        if self.logger.isEnabledFor(logging.DEBUG):
            message = self._format_structured_message(event, 'DEBUG', **context)
            self.logger.debug(message)

    def info(self, event: str, **context):
        """Log info message with structured data"""
        message = self._format_structured_message(event, 'INFO', **context)
        self.logger.info(message)

    def warning(self, event: str, **context):
        """Log warning message with structured data"""
        message = self._format_structured_message(event, 'WARNING', **context)
        self.logger.warning(message)

    def error(self, event: str, **context):
        """Log error message with structured data"""
        message = self._format_structured_message(event, 'ERROR', **context)
        self.logger.error(message)

    def exception(self, event: str, **context):
        """Log exception with structured data"""
        message = self._format_structured_message(event, 'ERROR', **context)
        self.logger.exception(message)


def log_execution_time(logger: Optional[StructuredLogger] = None, event_name: str = None):
    """
    Decorator to log execution time of a function

    Args:
        logger: StructuredLogger instance (creates one if None)
        event_name: Custom event name (defaults to function name)

    Example:
        @log_execution_time(logger=my_logger, event_name='trip_creation')
        def create_trip():
            # ... trip creation logic
            pass
    """
    def decorator(func):
        nonlocal logger, event_name

        if logger is None:
            logger = StructuredLogger(func.__module__)

        if event_name is None:
            event_name = f'function_execution.{func.__name__}'

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()

            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()

                logger.debug(
                    event_name,
                    function=func.__name__,
                    execution_time_seconds=execution_time,
                    status='success'
                )

                return result

            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()

                logger.error(
                    event_name,
                    function=func.__name__,
                    execution_time_seconds=execution_time,
                    status='error',
                    error_type=type(e).__name__,
                    error_message=str(e)
                )

                raise

        return wrapper
    return decorator


class LogContext:
    """Context manager for structured logging with automatic timing"""

    def __init__(
        self,
        logger: StructuredLogger,
        event: str,
        **initial_context
    ):
        """
        Initialize log context

        Args:
            logger: StructuredLogger instance
            event: Event name
            **initial_context: Initial context fields
        """
        self.logger = logger
        self.event = event
        self.context = initial_context
        self.start_time = None

    def __enter__(self):
        """Enter context and log start"""
        self.start_time = datetime.now()
        self.logger.debug(
            f'{self.event}.started',
            **self.context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and log completion with timing"""
        execution_time = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(
                f'{self.event}.completed',
                execution_time_seconds=execution_time,
                status='success',
                **self.context
            )
        else:
            self.logger.error(
                f'{self.event}.failed',
                execution_time_seconds=execution_time,
                status='error',
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **self.context
            )

        return False

    def update_context(self, **context):
        """Update context with additional fields"""
        self.context.update(context)


# Pre-configured loggers for common modules
trip_logger = StructuredLogger('shuttlebee.trip')
notification_logger = StructuredLogger('shuttlebee.notification')
passenger_logger = StructuredLogger('shuttlebee.passenger')
cron_logger = StructuredLogger('shuttlebee.cron')
api_logger = StructuredLogger('shuttlebee.api')

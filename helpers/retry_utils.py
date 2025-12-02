# -*- coding: utf-8 -*-
"""
Retry utilities with exponential backoff for API calls and external integrations
"""

import time
import random
import logging
from typing import Callable, Any, Optional, Type, Tuple
from functools import wraps

_logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt with exponential backoff

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            float: Delay in seconds
        """
        # Calculate exponential delay
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        # Add jitter if enabled (±25% randomness)
        if self.jitter:
            jitter_range = delay * 0.25
            delay = delay + random.uniform(-jitter_range, jitter_range)

        return max(0, delay)


def retry_with_backoff(
    max_retries: int = 3,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
    ignore_on: Tuple[Type[Exception], ...] = (),
    config: Optional[RetryConfig] = None,
    log_attempts: bool = True
):
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        retry_on: Tuple of exception types to retry on
        ignore_on: Tuple of exception types to never retry (re-raise immediately)
        config: Custom RetryConfig instance
        log_attempts: Whether to log retry attempts

    Example:
        @retry_with_backoff(max_retries=3, retry_on=(requests.RequestException,))
        def send_api_request():
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response
    """
    if config is None:
        config = RetryConfig(max_retries=max_retries)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except ignore_on as e:
                    # Re-raise immediately for ignored exceptions
                    if log_attempts:
                        _logger.warning(
                            f"Function {func.__name__} raised non-retryable exception: {type(e).__name__}"
                        )
                    raise

                except retry_on as e:
                    last_exception = e

                    # If this was the last attempt, raise the exception
                    if attempt >= config.max_retries:
                        if log_attempts:
                            _logger.error(
                                f"Function {func.__name__} failed after {attempt + 1} attempts: {str(e)}"
                            )
                        raise

                    # Calculate delay and wait
                    delay = config.get_delay(attempt)

                    if log_attempts:
                        _logger.warning(
                            f"Function {func.__name__} attempt {attempt + 1}/{config.max_retries + 1} "
                            f"failed: {str(e)}. Retrying in {delay:.2f}s..."
                        )

                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations with exponential backoff

    Example:
        retry_op = RetryableOperation(max_retries=3)
        with retry_op:
            response = requests.post(url, json=data)
            response.raise_for_status()
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_on: Tuple[Type[Exception], ...] = (Exception,),
        ignore_on: Tuple[Type[Exception], ...] = (),
        config: Optional[RetryConfig] = None,
        log_attempts: bool = True
    ):
        self.max_retries = max_retries
        self.retry_on = retry_on
        self.ignore_on = ignore_on
        self.config = config or RetryConfig(max_retries=max_retries)
        self.log_attempts = log_attempts
        self.attempt = 0
        self.last_exception = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return True

        # Don't retry on ignored exceptions
        if exc_type in self.ignore_on:
            return False

        # Check if this exception should be retried
        if not issubclass(exc_type, self.retry_on):
            return False

        self.last_exception = exc_val

        # If max retries exceeded, let exception propagate
        if self.attempt >= self.max_retries:
            if self.log_attempts:
                _logger.error(
                    f"Operation failed after {self.attempt + 1} attempts: {str(exc_val)}"
                )
            return False

        # Calculate delay and wait
        delay = self.config.get_delay(self.attempt)

        if self.log_attempts:
            _logger.warning(
                f"Operation attempt {self.attempt + 1}/{self.max_retries + 1} "
                f"failed: {str(exc_val)}. Retrying in {delay:.2f}s..."
            )

        time.sleep(delay)
        self.attempt += 1

        # Suppress exception to retry
        return True


def execute_with_retry(
    func: Callable,
    *args,
    max_retries: int = 3,
    retry_on: Tuple[Type[Exception], ...] = (Exception,),
    config: Optional[RetryConfig] = None,
    **kwargs
) -> Any:
    """
    Execute a function with retry logic

    Args:
        func: Function to execute
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        retry_on: Tuple of exception types to retry on
        config: Custom RetryConfig instance
        **kwargs: Keyword arguments for the function

    Returns:
        Any: Result of the function call

    Example:
        result = execute_with_retry(
            requests.post,
            url,
            json=data,
            max_retries=3,
            retry_on=(requests.RequestException,)
        )
    """
    if config is None:
        config = RetryConfig(max_retries=max_retries)

    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return func(*args, **kwargs)
        except retry_on as e:
            last_exception = e

            if attempt >= config.max_retries:
                _logger.error(
                    f"Function {func.__name__} failed after {attempt + 1} attempts: {str(e)}"
                )
                raise

            delay = config.get_delay(attempt)
            _logger.warning(
                f"Function {func.__name__} attempt {attempt + 1}/{config.max_retries + 1} "
                f"failed: {str(e)}. Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

    if last_exception:
        raise last_exception

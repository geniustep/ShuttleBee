# -*- coding: utf-8 -*-
"""
Rate limiting utilities for API calls and notifications
Prevents API quota exhaustion and service disruption
"""

import time
import logging
from typing import Dict, Optional, Callable
from datetime import datetime, timedelta
from collections import deque
from threading import Lock

_logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API calls
    Thread-safe implementation
    """

    def __init__(
        self,
        max_requests: int,
        time_window: int,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed per time window
            time_window: Time window in seconds
            burst_size: Maximum burst size (defaults to max_requests)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_size = burst_size or max_requests
        self.requests = deque()
        self.lock = Lock()

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed under rate limit

        Returns:
            bool: True if request is allowed, False otherwise
        """
        with self.lock:
            now = time.time()
            cutoff = now - self.time_window

            # Remove old requests outside time window
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            # Check if under limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    def wait_if_needed(self, timeout: Optional[float] = None) -> bool:
        """
        Wait until a request is allowed

        Args:
            timeout: Maximum time to wait in seconds (None = wait indefinitely)

        Returns:
            bool: True if request is now allowed, False if timeout reached
        """
        start_time = time.time()

        while not self.is_allowed():
            if timeout and (time.time() - start_time) >= timeout:
                return False

            # Calculate wait time until next slot is available
            with self.lock:
                if self.requests:
                    oldest = self.requests[0]
                    wait_time = (oldest + self.time_window) - time.time()
                    if wait_time > 0:
                        time.sleep(min(wait_time, 1.0))
                else:
                    time.sleep(0.1)

        return True

    def get_remaining_requests(self) -> int:
        """
        Get number of remaining requests in current window

        Returns:
            int: Number of remaining requests
        """
        with self.lock:
            now = time.time()
            cutoff = now - self.time_window

            # Remove old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            return max(0, self.max_requests - len(self.requests))

    def reset(self):
        """Reset rate limiter (clear all tracked requests)"""
        with self.lock:
            self.requests.clear()


class NotificationRateLimiter:
    """
    Rate limiter specifically for notification sending
    Manages limits per channel (SMS, WhatsApp, Email, Push)
    """

    def __init__(self):
        """Initialize notification rate limiter with default limits"""
        self.limiters = {
            'sms': RateLimiter(max_requests=100, time_window=60),  # 100 SMS per minute
            'whatsapp': RateLimiter(max_requests=80, time_window=60),  # 80 WhatsApp per minute
            'email': RateLimiter(max_requests=200, time_window=60),  # 200 emails per minute
            'push': RateLimiter(max_requests=500, time_window=60),  # 500 push per minute
        }
        self.lock = Lock()

    def configure_limit(self, channel: str, max_requests: int, time_window: int):
        """
        Configure rate limit for a specific channel

        Args:
            channel: Notification channel (sms, whatsapp, email, push)
            max_requests: Maximum requests per time window
            time_window: Time window in seconds
        """
        with self.lock:
            self.limiters[channel] = RateLimiter(max_requests, time_window)
            _logger.info(
                f'Configured rate limit for {channel}: '
                f'{max_requests} requests per {time_window}s'
            )

    def is_allowed(self, channel: str) -> bool:
        """
        Check if notification can be sent for channel

        Args:
            channel: Notification channel

        Returns:
            bool: True if allowed, False otherwise
        """
        limiter = self.limiters.get(channel)
        if not limiter:
            _logger.warning(f'No rate limiter configured for channel: {channel}')
            return True  # Allow if no limiter configured

        return limiter.is_allowed()

    def wait_and_send(
        self,
        channel: str,
        send_func: Callable,
        timeout: Optional[float] = 30.0
    ) -> bool:
        """
        Wait for rate limit and execute send function

        Args:
            channel: Notification channel
            send_func: Function to execute when allowed
            timeout: Maximum wait time in seconds

        Returns:
            bool: True if sent successfully, False if timeout
        """
        limiter = self.limiters.get(channel)
        if not limiter:
            _logger.warning(f'No rate limiter configured for channel: {channel}')
            send_func()
            return True

        if limiter.wait_if_needed(timeout=timeout):
            send_func()
            return True

        _logger.warning(
            f'Rate limit timeout for channel {channel} after {timeout}s'
        )
        return False

    def get_stats(self, channel: Optional[str] = None) -> Dict:
        """
        Get rate limiting statistics

        Args:
            channel: Specific channel (None = all channels)

        Returns:
            Dict: Statistics for channel(s)
        """
        stats = {}

        if channel:
            limiter = self.limiters.get(channel)
            if limiter:
                stats[channel] = {
                    'max_requests': limiter.max_requests,
                    'time_window': limiter.time_window,
                    'remaining': limiter.get_remaining_requests(),
                }
        else:
            for ch, limiter in self.limiters.items():
                stats[ch] = {
                    'max_requests': limiter.max_requests,
                    'time_window': limiter.time_window,
                    'remaining': limiter.get_remaining_requests(),
                }

        return stats


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts limits based on success/failure rates
    """

    def __init__(
        self,
        initial_max_requests: int,
        time_window: int,
        min_requests: int = 10,
        max_requests: int = 1000
    ):
        """
        Initialize adaptive rate limiter

        Args:
            initial_max_requests: Initial maximum requests
            time_window: Time window in seconds
            min_requests: Minimum allowed requests (safety limit)
            max_requests: Maximum allowed requests (safety limit)
        """
        self.current_max_requests = initial_max_requests
        self.time_window = time_window
        self.min_requests = min_requests
        self.max_requests_limit = max_requests
        self.limiter = RateLimiter(initial_max_requests, time_window)
        self.success_count = 0
        self.failure_count = 0
        self.lock = Lock()

    def record_success(self):
        """Record successful API call"""
        with self.lock:
            self.success_count += 1
            self._adjust_limits()

    def record_failure(self, is_rate_limit_error: bool = False):
        """
        Record failed API call

        Args:
            is_rate_limit_error: Whether failure was due to rate limiting
        """
        with self.lock:
            self.failure_count += 1

            # If rate limit error, immediately reduce limit
            if is_rate_limit_error:
                self._reduce_limit(factor=0.5)

            self._adjust_limits()

    def _adjust_limits(self):
        """Adjust rate limits based on success/failure ratio"""
        total_requests = self.success_count + self.failure_count

        # Need minimum sample size before adjusting
        if total_requests < 100:
            return

        success_rate = self.success_count / total_requests

        # Increase limit if high success rate
        if success_rate > 0.95:
            self._increase_limit(factor=1.1)
        # Decrease limit if low success rate
        elif success_rate < 0.85:
            self._reduce_limit(factor=0.9)

        # Reset counters after adjustment
        if total_requests >= 1000:
            self.success_count = 0
            self.failure_count = 0

    def _increase_limit(self, factor: float):
        """Increase rate limit by factor"""
        new_limit = int(self.current_max_requests * factor)
        new_limit = min(new_limit, self.max_requests_limit)

        if new_limit > self.current_max_requests:
            _logger.info(
                f'Increasing rate limit from {self.current_max_requests} '
                f'to {new_limit} requests per {self.time_window}s'
            )
            self.current_max_requests = new_limit
            self.limiter = RateLimiter(new_limit, self.time_window)

    def _reduce_limit(self, factor: float):
        """Reduce rate limit by factor"""
        new_limit = int(self.current_max_requests * factor)
        new_limit = max(new_limit, self.min_requests)

        if new_limit < self.current_max_requests:
            _logger.warning(
                f'Reducing rate limit from {self.current_max_requests} '
                f'to {new_limit} requests per {self.time_window}s'
            )
            self.current_max_requests = new_limit
            self.limiter = RateLimiter(new_limit, self.time_window)

    def is_allowed(self) -> bool:
        """Check if request is allowed"""
        return self.limiter.is_allowed()


# Global notification rate limiter instance
notification_rate_limiter = NotificationRateLimiter()

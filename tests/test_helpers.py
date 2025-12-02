# -*- coding: utf-8 -*-
"""
Unit tests for ShuttleBee Helper Utilities
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from odoo.tests import tagged
from odoo.exceptions import ValidationError, UserError
from odoo import fields

# Import helpers
from shuttlebee.helpers.validation import ValidationHelper
from shuttlebee.helpers.retry_utils import retry_with_backoff, RetryConfig
from shuttlebee.helpers.notification_providers import ProviderFactory, TwilioSMSProvider
from shuttlebee.helpers.logging_utils import StructuredLogger
from shuttlebee.helpers.conflict_detector import ConflictDetector
from shuttlebee.helpers.security_utils import template_renderer
from shuttlebee.helpers.rate_limiter import RateLimiter


@tagged('shuttlebee', 'helpers', 'post_install')
class TestValidationHelper(unittest.TestCase):
    """Test cases for ValidationHelper"""

    def test_validate_phone_basic(self):
        """Test basic phone validation"""
        # Valid phone numbers
        self.assertTrue(ValidationHelper.validate_phone("+212612345678", raise_error=False))
        self.assertTrue(ValidationHelper.validate_phone("212612345678", raise_error=False))
        self.assertTrue(ValidationHelper.validate_phone("0612345678", raise_error=False))
        
        # Invalid phone numbers
        self.assertFalse(ValidationHelper.validate_phone("123", raise_error=False))
        self.assertFalse(ValidationHelper.validate_phone("", raise_error=False))
        self.assertFalse(ValidationHelper.validate_phone(None, raise_error=False))

    def test_validate_phone_with_error(self):
        """Test phone validation with error raising"""
        with self.assertRaises(ValidationError):
            ValidationHelper.validate_phone("123", raise_error=True)
        
        with self.assertRaises(ValidationError):
            ValidationHelper.validate_phone("", raise_error=True)

    def test_validate_email(self):
        """Test email validation"""
        # Valid emails
        self.assertTrue(ValidationHelper.validate_email("user@example.com", raise_error=False))
        self.assertTrue(ValidationHelper.validate_email("test.user@domain.co.uk", raise_error=False))
        
        # Invalid emails
        self.assertFalse(ValidationHelper.validate_email("invalid-email", raise_error=False))
        self.assertFalse(ValidationHelper.validate_email("@example.com", raise_error=False))
        self.assertFalse(ValidationHelper.validate_email("user@", raise_error=False))

    def test_validate_coordinates(self):
        """Test coordinate validation"""
        # Valid coordinates
        self.assertTrue(ValidationHelper.validate_coordinates(33.5731, -7.5898, raise_error=False))
        self.assertTrue(ValidationHelper.validate_coordinates(-90.0, 180.0, raise_error=False))
        
        # Invalid coordinates
        self.assertFalse(ValidationHelper.validate_coordinates(100.0, -7.5898, raise_error=False))  # Lat > 90
        self.assertFalse(ValidationHelper.validate_coordinates(33.5731, 200.0, raise_error=False))  # Lon > 180
        self.assertFalse(ValidationHelper.validate_coordinates(-100.0, -7.5898, raise_error=False))  # Lat < -90


@tagged('shuttlebee', 'helpers', 'post_install')
class TestRetryUtils(unittest.TestCase):
    """Test cases for RetryUtils"""

    def test_retry_config(self):
        """Test RetryConfig"""
        config = RetryConfig(
            max_retries=5,
            initial_delay=2.0,
            max_delay=120.0,
            exponential_base=2.0
        )
        
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.initial_delay, 2.0)
        
        # Test delay calculation
        delay1 = config.get_delay(0)
        delay2 = config.get_delay(1)
        delay3 = config.get_delay(2)
        
        self.assertGreater(delay2, delay1)
        self.assertGreater(delay3, delay2)

    @patch('time.sleep')
    def test_retry_decorator_success(self, mock_sleep):
        """Test retry decorator with successful call"""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3)
        def successful_function():
            call_count[0] += 1
            return "success"
        
        result = successful_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 1)
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    def test_retry_decorator_failure_then_success(self, mock_sleep):
        """Test retry decorator with failure then success"""
        call_count = [0]
        
        @retry_with_backoff(max_retries=3, initial_delay=0.1)
        def flaky_function():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = flaky_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count[0], 2)
        self.assertEqual(mock_sleep.call_count, 1)


@tagged('shuttlebee', 'helpers', 'post_install')
class TestNotificationProviders(unittest.TestCase):
    """Test cases for NotificationProviders"""

    @patch('requests.post')
    def test_twilio_sms_provider(self, mock_post):
        """Test Twilio SMS provider"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'sid': 'SM1234567890',
            'status': 'queued'
        }
        mock_post.return_value = mock_response
        
        provider = TwilioSMSProvider(
            api_url='https://api.twilio.com/2010-04-01/Accounts/ACxxx/Messages.json',
            api_key='account_sid',
            api_secret='auth_token'
        )
        
        response = provider.send('+212612345678', 'Test message')
        
        self.assertEqual(response['message_id'], 'SM1234567890')
        self.assertEqual(response['status'], 'sent')
        mock_post.assert_called_once()

    def test_provider_factory(self):
        """Test ProviderFactory"""
        # Test creating Twilio provider
        provider = ProviderFactory.create_provider(
            provider_type='twilio_sms',
            api_url='https://api.twilio.com/...',
            api_key='account_sid',
            api_secret='auth_token'
        )
        
        self.assertIsInstance(provider, TwilioSMSProvider)

    @patch('requests.post')
    def test_provider_error_handling(self, mock_post):
        """Test provider error handling"""
        mock_post.side_effect = Exception("Network error")
        
        provider = TwilioSMSProvider(
            api_url='https://api.twilio.com/...',
            api_key='account_sid',
            api_secret='auth_token'
        )
        
        with self.assertRaises(UserError):
            provider.send('+212612345678', 'Test message')


@tagged('shuttlebee', 'helpers', 'post_install')
class TestLoggingUtils(unittest.TestCase):
    """Test cases for LoggingUtils"""

    def test_structured_logger(self):
        """Test StructuredLogger"""
        logger = StructuredLogger('test.logger')
        
        # Test basic logging
        with patch('logging.Logger.info') as mock_info:
            logger.info('test_event', extra={'key': 'value'})
            mock_info.assert_called_once()

    def test_logger_measure_time(self):
        """Test time measurement context manager"""
        logger = StructuredLogger('test.logger')
        
        with patch('logging.Logger.info') as mock_info:
            with logger.measure_time('test_operation'):
                pass  # Simulate operation
            
            # Verify that timing was logged
            self.assertTrue(mock_info.called)


@tagged('shuttlebee', 'helpers', 'post_install')
class TestConflictDetector(unittest.TestCase):
    """Test cases for ConflictDetector"""

    def setUp(self):
        """Set up test fixtures"""
        self.trip_model = Mock()
        self.detector = ConflictDetector(self.trip_model)

    def test_check_vehicle_conflict_no_conflict(self):
        """Test vehicle conflict check with no conflict"""
        self.trip_model.search.return_value = []
        
        has_conflict, conflict_data = self.detector.check_vehicle_conflict(
            vehicle_id=1,
            trip_date=datetime.now().date(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2)
        )
        
        self.assertFalse(has_conflict)
        self.assertIsNone(conflict_data)

    def test_check_vehicle_conflict_with_conflict(self):
        """Test vehicle conflict check with conflict"""
        conflicting_trip = Mock()
        conflicting_trip.id = 2
        conflicting_trip.name = "Conflicting Trip"
        
        self.trip_model.search.return_value = [conflicting_trip]
        
        has_conflict, conflict_data = self.detector.check_vehicle_conflict(
            vehicle_id=1,
            trip_date=datetime.now().date(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2)
        )
        
        self.assertTrue(has_conflict)
        self.assertIsNotNone(conflict_data)
        self.assertEqual(conflict_data['conflicting_trip'], conflicting_trip)


@tagged('shuttlebee', 'helpers', 'post_install')
class TestSecurityUtils(unittest.TestCase):
    """Test cases for SecurityUtils"""

    def test_template_renderer(self):
        """Test safe template rendering"""
        template = "Hello {{ name }}!"
        context = {'name': 'World'}
        
        result = template_renderer.render(template, context)
        self.assertEqual(result, "Hello World!")

    def test_template_renderer_xss_protection(self):
        """Test XSS protection in template rendering"""
        template = "{{ user_input }}"
        context = {'user_input': '<script>alert("XSS")</script>'}
        
        result = template_renderer.render(template, context)
        # Should escape HTML
        self.assertNotIn('<script>', result)


@tagged('shuttlebee', 'helpers', 'post_install')
class TestRateLimiter(unittest.TestCase):
    """Test cases for RateLimiter"""

    def test_rate_limiter_basic(self):
        """Test basic rate limiting"""
        limiter = RateLimiter(rate_per_minute=60, burst_size=10)
        
        # Should allow sending
        self.assertTrue(limiter.can_send('test_channel'))
        
        # Consume tokens
        for _ in range(10):
            limiter.consume('test_channel')
        
        # Should still allow (within burst)
        self.assertTrue(limiter.can_send('test_channel'))

    def test_rate_limiter_exceeded(self):
        """Test rate limit exceeded"""
        limiter = RateLimiter(rate_per_minute=1, burst_size=1)
        
        # Consume token
        limiter.consume('test_channel')
        
        # Should not allow immediately
        self.assertFalse(limiter.can_send('test_channel'))
        
        # Wait time should be positive
        wait_time = limiter.get_wait_time('test_channel')
        self.assertGreater(wait_time, 0)


@tagged('shuttlebee', 'integration', 'post_install')
class TestIntegration(unittest.TestCase):
    """Integration tests for helper utilities working together"""

    @patch('requests.post')
    @patch('time.sleep')
    def test_send_notification_with_all_helpers(self, mock_sleep, mock_post):
        """Test sending notification using all helper utilities"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'sid': 'SM123', 'status': 'queued'}
        mock_post.return_value = mock_response
        
        # Create rate limiter
        limiter = RateLimiter(rate_per_minute=60, burst_size=10)
        
        # Validate phone
        phone = "+212612345678"
        ValidationHelper.validate_phone(phone, raise_error=True)
        
        # Check rate limit
        self.assertTrue(limiter.can_send('sms'))
        
        # Create provider
        provider = ProviderFactory.create_provider(
            provider_type='twilio_sms',
            api_url='https://api.twilio.com/...',
            api_key='account_sid',
            api_secret='auth_token'
        )
        
        # Send with retry
        @retry_with_backoff(max_retries=3)
        def send():
            response = provider.send(phone, 'Test message')
            limiter.consume('sms')
            return response
        
        response = send()
        
        self.assertEqual(response['message_id'], 'SM123')
        mock_post.assert_called_once()


if __name__ == '__main__':
    unittest.main()


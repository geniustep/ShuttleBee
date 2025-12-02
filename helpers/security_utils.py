# -*- coding: utf-8 -*-
"""
Security utilities for credential management and safe template rendering
"""

import logging
import base64
from typing import Any, Dict, Optional, Tuple
from jinja2 import Template, Environment, StrictUndefined, select_autoescape
from jinja2.exceptions import TemplateError
from odoo.exceptions import UserError
from odoo import _

_logger = logging.getLogger(__name__)


class CredentialManager:
    """Secure credential storage and retrieval"""

    @staticmethod
    def encrypt_value(value: str, key: Optional[str] = None) -> str:
        """
        Encrypt a sensitive value (basic implementation)

        Note: This is a basic implementation. For production, use proper
        encryption libraries like cryptography.fernet

        Args:
            value: Value to encrypt
            key: Encryption key (optional, uses default if None)

        Returns:
            str: Base64-encoded encrypted value
        """
        if not value:
            return ''

        try:
            # Basic encoding (for demonstration - use proper encryption in production!)
            encoded = base64.b64encode(value.encode('utf-8')).decode('utf-8')
            return f'encrypted:{encoded}'
        except Exception as e:
            _logger.error(f'Failed to encrypt value: {str(e)}')
            raise UserError(_('Failed to encrypt sensitive data'))

    @staticmethod
    def decrypt_value(encrypted_value: str, key: Optional[str] = None) -> str:
        """
        Decrypt an encrypted value

        Args:
            encrypted_value: Encrypted value to decrypt
            key: Decryption key (optional, uses default if None)

        Returns:
            str: Decrypted value
        """
        if not encrypted_value:
            return ''

        try:
            # Check if value is actually encrypted
            if not encrypted_value.startswith('encrypted:'):
                _logger.warning('Value is not encrypted, returning as-is')
                return encrypted_value

            # Remove prefix and decode
            encoded = encrypted_value[10:]  # Remove 'encrypted:' prefix
            decoded = base64.b64decode(encoded.encode('utf-8')).decode('utf-8')
            return decoded

        except Exception as e:
            _logger.error(f'Failed to decrypt value: {str(e)}')
            raise UserError(_('Failed to decrypt sensitive data'))

    @staticmethod
    def mask_sensitive_value(value: str, visible_chars: int = 4) -> str:
        """
        Mask sensitive value for logging

        Args:
            value: Value to mask
            visible_chars: Number of characters to keep visible

        Returns:
            str: Masked value (e.g., "****5678")
        """
        if not value:
            return ''

        if len(value) <= visible_chars:
            return '*' * len(value)

        masked_part = '*' * (len(value) - visible_chars)
        visible_part = value[-visible_chars:]
        return f'{masked_part}{visible_part}'


class SafeTemplateRenderer:
    """
    Safe template rendering to prevent injection attacks
    Uses Jinja2 with strict undefined variables and autoescaping
    """

    def __init__(self, autoescape: bool = True):
        """
        Initialize safe template renderer

        Args:
            autoescape: Whether to automatically escape HTML
        """
        self.env = Environment(
            undefined=StrictUndefined,
            autoescape=select_autoescape(['html', 'xml']) if autoescape else False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_string: str, context: Dict[str, Any]) -> str:
        """
        Render template with safe context

        Args:
            template_string: Template string with Jinja2 syntax
            context: Context dictionary for template variables

        Returns:
            str: Rendered template

        Raises:
            UserError: If template rendering fails
        """
        if not template_string:
            return ''

        try:
            # Sanitize context to prevent code injection
            safe_context = self._sanitize_context(context)

            # Render template
            template = self.env.from_string(template_string)
            return template.render(**safe_context)

        except TemplateError as e:
            _logger.error(f'Template rendering error: {str(e)}')
            raise UserError(
                _('Failed to render message template: %s') % str(e)
            )
        except Exception as e:
            _logger.error(f'Unexpected error in template rendering: {str(e)}', exc_info=True)
            raise UserError(_('Failed to render message template'))

    def render_notification_message(
        self,
        template_string: str,
        trip=None,
        passenger=None,
        driver=None,
        **extra_context
    ) -> str:
        """
        Render notification message with standard context

        Args:
            template_string: Template string
            trip: Trip record
            passenger: Passenger record
            driver: Driver record
            **extra_context: Additional context variables

        Returns:
            str: Rendered message
        """
        context = {}

        if trip:
            context.update({
                'trip_name': trip.name or '',
                'trip_date': trip.date.strftime('%Y-%m-%d') if trip.date else '',
                'trip_time': trip.planned_start_time.strftime('%H:%M') if trip.planned_start_time else '',
                'trip_type': dict(trip._fields['trip_type'].selection).get(trip.trip_type, ''),
            })

        if passenger:
            context.update({
                'passenger_name': passenger.name or '',
                'passenger_phone': passenger.phone or passenger.mobile or '',
            })

        if driver:
            context.update({
                'driver_name': driver.name or '',
                'driver_phone': driver.phone or driver.mobile or '',
            })

        context.update(extra_context)

        return self.render(template_string, context)

    @staticmethod
    def _sanitize_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize context to prevent injection attacks

        Args:
            context: Original context dictionary

        Returns:
            Dict: Sanitized context
        """
        safe_context = {}

        for key, value in context.items():
            # Only allow safe types
            if isinstance(value, (str, int, float, bool, type(None))):
                safe_context[key] = value
            elif hasattr(value, 'name'):
                # For Odoo records, use safe attributes
                safe_context[key] = str(value.name)
            else:
                # Convert to string for safety
                safe_context[key] = str(value)

        return safe_context

    @staticmethod
    def validate_template(template_string: str) -> Tuple[bool, Optional[str]]:
        """
        Validate template syntax without rendering

        Args:
            template_string: Template string to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not template_string:
            return True, None

        try:
            env = Environment(undefined=StrictUndefined)
            env.from_string(template_string)
            return True, None
        except TemplateError as e:
            return False, str(e)


# Singleton instances for convenience
template_renderer = SafeTemplateRenderer(autoescape=True)
credential_manager = CredentialManager()


from typing import Tuple  # Add this import at the top of the file

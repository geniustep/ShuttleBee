# -*- coding: utf-8 -*-
"""
Centralized validation utilities for ShuttleBee
Provides reusable validation methods for phone numbers, emails, coordinates, etc.
"""

import re
import logging
from typing import Optional, Tuple
from odoo.exceptions import ValidationError
from odoo import _

_logger = logging.getLogger(__name__)

try:
    import phonenumbers
    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False
    _logger.warning(
        'phonenumbers library not installed. Using basic phone validation. '
        'Install with: pip install phonenumbers'
    )


class ValidationHelper:
    """Centralized validation helper for common validations"""

    @staticmethod
    def validate_phone(phone: str, country_code: str = 'MA', raise_error: bool = True) -> bool:
        """
        Validate phone number format with proper international validation

        Args:
            phone: Phone number to validate
            country_code: ISO country code (default: MA for Morocco)
            raise_error: Whether to raise ValidationError on failure

        Returns:
            bool: True if valid, False otherwise

        Raises:
            ValidationError: If raise_error=True and validation fails
        """
        if not phone:
            if raise_error:
                raise ValidationError(_('Phone number is required!'))
            return False

        # Use phonenumbers library if available
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed = phonenumbers.parse(phone, country_code)
                is_valid = phonenumbers.is_valid_number(parsed)

                if not is_valid and raise_error:
                    raise ValidationError(
                        _('Invalid phone number: %s. Please provide a valid phone number.') % phone
                    )
                return is_valid

            except phonenumbers.NumberParseException as e:
                if raise_error:
                    raise ValidationError(
                        _('Failed to parse phone number: %s. Error: %s') % (phone, str(e))
                    )
                return False

        # Fallback to basic validation if phonenumbers not available
        phone_clean = re.sub(r'[\s\-\(\)\+]', '', phone)
        is_valid = bool(re.match(r'^\d{7,15}$', phone_clean))

        if not is_valid and raise_error:
            raise ValidationError(
                _('Invalid phone number format: %s. Expected 7-15 digits.') % phone
            )
        return is_valid

    @staticmethod
    def validate_email(email: str, raise_error: bool = True) -> bool:
        """
        Validate email format

        Args:
            email: Email address to validate
            raise_error: Whether to raise ValidationError on failure

        Returns:
            bool: True if valid, False otherwise

        Raises:
            ValidationError: If raise_error=True and validation fails
        """
        if not email:
            if raise_error:
                raise ValidationError(_('Email address is required!'))
            return False

        # RFC 5322 compliant email regex (simplified)
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(pattern, email))

        if not is_valid and raise_error:
            raise ValidationError(_('Invalid email format: %s') % email)
        return is_valid

    @staticmethod
    def validate_coordinates(
        latitude: float,
        longitude: float,
        raise_error: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate GPS coordinates

        Args:
            latitude: Latitude value
            longitude: Longitude value
            raise_error: Whether to raise ValidationError on failure

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)

        Raises:
            ValidationError: If raise_error=True and validation fails
        """
        errors = []

        try:
            lat = float(latitude)
            lng = float(longitude)
        except (TypeError, ValueError):
            error_msg = _('Latitude and longitude must be numeric values')
            if raise_error:
                raise ValidationError(error_msg)
            return False, error_msg

        if not (-90 <= lat <= 90):
            errors.append(_('Latitude must be between -90 and 90'))

        if not (-180 <= lng <= 180):
            errors.append(_('Longitude must be between -180 and 180'))

        if errors:
            error_msg = '; '.join(errors)
            if raise_error:
                raise ValidationError(error_msg)
            return False, error_msg

        return True, None

    @staticmethod
    def clean_phone(phone: str) -> str:
        """
        Clean phone number by removing formatting characters

        Args:
            phone: Phone number to clean

        Returns:
            str: Cleaned phone number (digits only)
        """
        if not phone:
            return ''

        # Remove common separators and spaces
        phone_clean = re.sub(r'[\s\-\(\)]', '', phone)

        # Remove leading + if present
        if phone_clean.startswith('+'):
            phone_clean = phone_clean[1:]

        return phone_clean

    @staticmethod
    def validate_contact_info(channel: str, phone: Optional[str] = None,
                            email: Optional[str] = None, raise_error: bool = True) -> bool:
        """
        Validate contact information based on channel

        Args:
            channel: Communication channel (sms, whatsapp, email, push)
            phone: Phone number (required for sms/whatsapp)
            email: Email address (required for email)
            raise_error: Whether to raise ValidationError on failure

        Returns:
            bool: True if valid, False otherwise

        Raises:
            ValidationError: If raise_error=True and validation fails
        """
        if channel in ['sms', 'whatsapp']:
            if not phone:
                if raise_error:
                    raise ValidationError(
                        _('Phone number is required for %s notifications!') % channel.upper()
                    )
                return False
            return ValidationHelper.validate_phone(phone, raise_error=raise_error)

        elif channel == 'email':
            if not email:
                if raise_error:
                    raise ValidationError(_('Email address is required for email notifications!'))
                return False
            return ValidationHelper.validate_email(email, raise_error=raise_error)

        elif channel == 'push':
            # Push notifications don't require phone/email validation
            return True

        else:
            if raise_error:
                raise ValidationError(_('Unknown notification channel: %s') % channel)
            return False

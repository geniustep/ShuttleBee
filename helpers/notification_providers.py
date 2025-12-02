# -*- coding: utf-8 -*-
"""
Notification Provider Adapters for SMS, WhatsApp, Email, and Push notifications
Provides a clean abstraction layer for different notification services
"""

import logging
import requests
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from odoo.exceptions import UserError
from odoo import _

_logger = logging.getLogger(__name__)


class NotificationProvider(ABC):
    """Abstract base class for notification providers"""

    def __init__(self, api_url: str, api_key: str, **config):
        """
        Initialize notification provider

        Args:
            api_url: API endpoint URL
            api_key: API authentication key
            **config: Additional configuration parameters
        """
        self.api_url = api_url
        self.api_key = api_key
        self.config = config
        self.timeout = config.get('timeout', 10)

    @abstractmethod
    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Send notification

        Args:
            recipient: Recipient identifier (phone, email, etc.)
            message: Message content
            **kwargs: Additional parameters

        Returns:
            Dict with response data including message_id, status, etc.

        Raises:
            UserError: If sending fails
        """
        pass

    @abstractmethod
    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Format API payload specific to this provider

        Args:
            recipient: Recipient identifier
            message: Message content
            **kwargs: Additional parameters

        Returns:
            Dict with formatted payload
        """
        pass

    def validate_config(self) -> bool:
        """
        Validate provider configuration

        Returns:
            bool: True if configuration is valid

        Raises:
            UserError: If configuration is invalid
        """
        if not self.api_url:
            raise UserError(_('API URL is not configured for %s') % self.__class__.__name__)
        if not self.api_key:
            raise UserError(_('API key is not configured for %s') % self.__class__.__name__)
        return True


class TwilioSMSProvider(NotificationProvider):
    """Twilio SMS provider implementation"""

    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Format payload for Twilio API"""
        from_number = self.config.get('from_number')
        if not from_number:
            raise UserError(_('Twilio from_number is not configured'))

        return {
            'From': from_number,
            'To': recipient,
            'Body': message,
        }

    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send SMS via Twilio"""
        self.validate_config()

        payload = self.format_payload(recipient, message, **kwargs)

        try:
            response = requests.post(
                f"{self.api_url}/Messages.json",
                data=payload,
                auth=(self.config.get('account_sid'), self.api_key),
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            return {
                'provider_message_id': data.get('sid'),
                'status': data.get('status'),
                'api_response': response.text[:200],
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send SMS via Twilio: %s') % str(e))


class GenericSMSProvider(NotificationProvider):
    """Generic SMS provider for custom implementations"""

    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Format generic SMS payload"""
        return {
            'to': recipient,
            'message': message,
            'api_key': self.api_key,
        }

    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send SMS via generic API"""
        self.validate_config()

        payload = self.format_payload(recipient, message, **kwargs)

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            response.raise_for_status()

            return {
                'provider_message_id': response.headers.get('X-Message-Id'),
                'api_response': f'SMS sent successfully. Response: {response.text[:200]}',
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send SMS: %s') % str(e))


class WhatsAppBusinessProvider(NotificationProvider):
    """WhatsApp Business API provider"""

    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Format WhatsApp Business API payload"""
        phone_number_id = self.config.get('phone_number_id')
        if not phone_number_id:
            raise UserError(_('WhatsApp phone_number_id is not configured'))

        return {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': recipient,
            'type': 'text',
            'text': {
                'preview_url': False,
                'body': message
            }
        }

    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send WhatsApp message via Business API"""
        self.validate_config()

        payload = self.format_payload(recipient, message, **kwargs)
        phone_number_id = self.config.get('phone_number_id')

        try:
            response = requests.post(
                f"{self.api_url}/{phone_number_id}/messages",
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            return {
                'provider_message_id': data.get('messages', [{}])[0].get('id'),
                'api_response': f'WhatsApp sent successfully. Response: {response.text[:200]}',
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send WhatsApp: %s') % str(e))


class GenericWhatsAppProvider(NotificationProvider):
    """Generic WhatsApp provider for custom implementations"""

    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Format generic WhatsApp payload"""
        return {
            'to': recipient,
            'message': message,
            'api_key': self.api_key,
        }

    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send WhatsApp via generic API"""
        self.validate_config()

        payload = self.format_payload(recipient, message, **kwargs)

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.timeout
            )
            response.raise_for_status()

            return {
                'provider_message_id': response.headers.get('X-Message-Id'),
                'api_response': f'WhatsApp sent successfully. Response: {response.text[:200]}',
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send WhatsApp: %s') % str(e))


class FirebasePushProvider(NotificationProvider):
    """Firebase Cloud Messaging (FCM) provider for push notifications"""

    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Format FCM payload"""
        title = kwargs.get('title', 'ShuttleBee Notification')
        notification_type = kwargs.get('notification_type', 'custom')
        trip_id = kwargs.get('trip_id')

        return {
            'to': recipient,  # FCM token
            'notification': {
                'title': title,
                'body': message,
                'sound': 'default',
            },
            'data': {
                'trip_id': str(trip_id) if trip_id else None,
                'notification_type': notification_type,
                'click_action': 'FLUTTER_NOTIFICATION_CLICK',
            },
            'priority': 'high',
        }

    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """Send push notification via FCM"""
        self.validate_config()

        payload = self.format_payload(recipient, message, **kwargs)

        try:
            response = requests.post(
                f"{self.api_url}/fcm/send",
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'key={self.api_key}'
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            return {
                'provider_message_id': data.get('message_id'),
                'api_response': f'Push notification sent successfully. Response: {response.text[:200]}',
            }

        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send push notification: %s') % str(e))


class ProviderFactory:
    """Factory for creating notification provider instances"""

    PROVIDERS = {
        'twilio_sms': TwilioSMSProvider,
        'generic_sms': GenericSMSProvider,
        'whatsapp_business': WhatsAppBusinessProvider,
        'generic_whatsapp': GenericWhatsAppProvider,
        'firebase_push': FirebasePushProvider,
    }

    @classmethod
    def create_provider(
        cls,
        provider_type: str,
        api_url: str,
        api_key: str,
        **config
    ) -> NotificationProvider:
        """
        Create notification provider instance

        Args:
            provider_type: Type of provider (twilio_sms, generic_sms, etc.)
            api_url: API endpoint URL
            api_key: API authentication key
            **config: Additional configuration

        Returns:
            NotificationProvider: Provider instance

        Raises:
            ValueError: If provider_type is not supported
        """
        provider_class = cls.PROVIDERS.get(provider_type)

        if not provider_class:
            raise ValueError(
                _('Unknown provider type: %s. Available: %s') % (
                    provider_type,
                    ', '.join(cls.PROVIDERS.keys())
                )
            )

        return provider_class(api_url, api_key, **config)

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """
        Register a custom provider

        Args:
            name: Provider name
            provider_class: Provider class (must inherit from NotificationProvider)
        """
        if not issubclass(provider_class, NotificationProvider):
            raise ValueError('Provider class must inherit from NotificationProvider')

        cls.PROVIDERS[name] = provider_class
        _logger.info(f'Registered custom notification provider: {name}')

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


class WAHAWhatsAppProvider(NotificationProvider):
    """
    WAHA (WhatsApp HTTP API) Provider
    Documentation: https://waha.devlike.pro/docs/overview/introduction/
    
    WAHA is a self-hosted WhatsApp API that provides endpoints for:
    - Session management (create, start, stop, QR code)
    - Sending messages (text, image, file, voice, video, location)
    - Receiving webhooks for incoming messages and status updates
    """

    def __init__(self, api_url: str, api_key: str, **config):
        """
        Initialize WAHA provider
        
        Args:
            api_url: WAHA API base URL (e.g., http://localhost:3000)
            api_key: WAHA API key for authentication
            **config: Additional configuration:
                - session: Session name (default: 'default')
                - timeout: Request timeout in seconds (default: 30)
        """
        super().__init__(api_url, api_key, **config)
        self.session = config.get('session', 'default')
        self.timeout = config.get('timeout', 30)

    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for WAHA API requests"""
        return {
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key,
        }

    def _format_phone_number(self, phone: str) -> str:
        """
        Format phone number for WAHA API (chatId format)
        WAHA expects: {phone}@c.us for individual chats
        
        Args:
            phone: Phone number (can include + or country code)
            
        Returns:
            Formatted chatId for WAHA
        """
        # Remove all non-digit characters
        clean_phone = ''.join(filter(str.isdigit, phone))
        # WAHA format: phone@c.us
        return f"{clean_phone}@c.us"

    def format_payload(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Format payload for WAHA sendText endpoint
        
        Args:
            recipient: Phone number
            message: Text message content
            **kwargs: Additional options (reply_to, mentions, etc.)
            
        Returns:
            Formatted payload for WAHA API
        """
        chat_id = self._format_phone_number(recipient)
        
        payload = {
            'chatId': chat_id,
            'text': message,
            'session': self.session,
        }
        
        # Optional: reply to a specific message
        if kwargs.get('reply_to'):
            payload['reply_to'] = kwargs['reply_to']
            
        # Optional: link preview
        if kwargs.get('link_preview', True):
            payload['linkPreview'] = True
            
        return payload

    def send(self, recipient: str, message: str, **kwargs) -> Dict[str, Any]:
        """
        Send text message via WAHA API
        
        Endpoint: POST /api/sendText
        
        Args:
            recipient: Phone number
            message: Text message
            **kwargs: Additional options
            
        Returns:
            Dict with provider_message_id and api_response
        """
        self.validate_config()
        
        payload = self.format_payload(recipient, message, **kwargs)
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sendText",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # WAHA returns message ID in the response
            message_id = data.get('id') or data.get('key', {}).get('id')
            
            return {
                'provider_message_id': message_id,
                'api_response': f'WAHA: Message sent successfully. ID: {message_id}',
                'raw_response': data,
            }
            
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', str(e))
            except:
                pass
            raise UserError(_('WAHA API Error: %s') % error_msg)
        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send WhatsApp via WAHA: %s') % str(e))

    def send_image(self, recipient: str, image_url: str, caption: str = '', **kwargs) -> Dict[str, Any]:
        """
        Send image via WAHA API
        
        Endpoint: POST /api/sendImage
        
        Args:
            recipient: Phone number
            image_url: URL of the image to send
            caption: Optional caption for the image
            **kwargs: Additional options
            
        Returns:
            Dict with provider_message_id and api_response
        """
        self.validate_config()
        
        chat_id = self._format_phone_number(recipient)
        
        payload = {
            'chatId': chat_id,
            'file': {
                'url': image_url,
            },
            'caption': caption,
            'session': self.session,
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sendImage",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('id') or data.get('key', {}).get('id')
            
            return {
                'provider_message_id': message_id,
                'api_response': f'WAHA: Image sent successfully. ID: {message_id}',
                'raw_response': data,
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send image via WAHA: %s') % str(e))

    def send_file(self, recipient: str, file_url: str, filename: str = '', caption: str = '', **kwargs) -> Dict[str, Any]:
        """
        Send file via WAHA API
        
        Endpoint: POST /api/sendFile
        
        Args:
            recipient: Phone number
            file_url: URL of the file to send
            filename: Optional filename
            caption: Optional caption
            **kwargs: Additional options
            
        Returns:
            Dict with provider_message_id and api_response
        """
        self.validate_config()
        
        chat_id = self._format_phone_number(recipient)
        
        payload = {
            'chatId': chat_id,
            'file': {
                'url': file_url,
            },
            'session': self.session,
        }
        
        if filename:
            payload['file']['filename'] = filename
        if caption:
            payload['caption'] = caption
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sendFile",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('id') or data.get('key', {}).get('id')
            
            return {
                'provider_message_id': message_id,
                'api_response': f'WAHA: File sent successfully. ID: {message_id}',
                'raw_response': data,
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send file via WAHA: %s') % str(e))

    def send_location(self, recipient: str, latitude: float, longitude: float, name: str = '', address: str = '', **kwargs) -> Dict[str, Any]:
        """
        Send location via WAHA API
        
        Endpoint: POST /api/sendLocation
        
        Args:
            recipient: Phone number
            latitude: Location latitude
            longitude: Location longitude
            name: Optional location name
            address: Optional location address
            **kwargs: Additional options
            
        Returns:
            Dict with provider_message_id and api_response
        """
        self.validate_config()
        
        chat_id = self._format_phone_number(recipient)
        
        payload = {
            'chatId': chat_id,
            'latitude': latitude,
            'longitude': longitude,
            'session': self.session,
        }
        
        if name:
            payload['name'] = name
        if address:
            payload['address'] = address
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sendLocation",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            message_id = data.get('id') or data.get('key', {}).get('id')
            
            return {
                'provider_message_id': message_id,
                'api_response': f'WAHA: Location sent successfully. ID: {message_id}',
                'raw_response': data,
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send location via WAHA: %s') % str(e))

    def send_seen(self, chat_id: str, message_id: str, **kwargs) -> Dict[str, Any]:
        """
        Mark message as seen/read
        
        Endpoint: POST /api/sendSeen
        
        Args:
            chat_id: Chat ID
            message_id: Message ID to mark as seen
            **kwargs: Additional options
            
        Returns:
            Dict with api_response
        """
        self.validate_config()
        
        payload = {
            'chatId': chat_id,
            'messageId': message_id,
            'session': self.session,
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/api/sendSeen",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return {
                'api_response': 'WAHA: Message marked as seen',
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(_('Failed to send seen status via WAHA: %s') % str(e))

    def start_typing(self, recipient: str, **kwargs) -> Dict[str, Any]:
        """
        Start typing indicator
        
        Endpoint: POST /api/startTyping
        """
        self.validate_config()
        
        chat_id = self._format_phone_number(recipient)
        
        payload = {
            'chatId': chat_id,
            'session': self.session,
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/api/startTyping",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return {
                'api_response': 'WAHA: Typing started',
            }
            
        except requests.exceptions.RequestException as e:
            _logger.warning(f'Failed to start typing: {e}')
            return {'api_response': f'Warning: {e}'}

    def stop_typing(self, recipient: str, **kwargs) -> Dict[str, Any]:
        """
        Stop typing indicator
        
        Endpoint: POST /api/stopTyping
        """
        self.validate_config()
        
        chat_id = self._format_phone_number(recipient)
        
        payload = {
            'chatId': chat_id,
            'session': self.session,
        }
        
        try:
            response = requests.post(
                f"{self.api_url}/api/stopTyping",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return {
                'api_response': 'WAHA: Typing stopped',
            }
            
        except requests.exceptions.RequestException as e:
            _logger.warning(f'Failed to stop typing: {e}')
            return {'api_response': f'Warning: {e}'}


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
        'waha_whatsapp': WAHAWhatsAppProvider,
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

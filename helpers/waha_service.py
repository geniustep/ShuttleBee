# -*- coding: utf-8 -*-
"""
WAHA (WhatsApp HTTP API) Service
Comprehensive service for managing WAHA sessions and advanced WhatsApp operations

Documentation: https://waha.devlike.pro/docs/overview/introduction/
GitHub: https://github.com/devlikeapro/waha

API Endpoints:
- Sessions: /api/sessions - Manage WhatsApp sessions
- Auth: /api/{session}/auth/qr - QR code for pairing
- Chatting: /api/sendText, /api/sendImage, etc.
"""

import logging
import requests
import base64
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

_logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """WAHA Session Status"""
    STOPPED = 'STOPPED'
    STARTING = 'STARTING'
    SCAN_QR_CODE = 'SCAN_QR_CODE'
    WORKING = 'WORKING'
    FAILED = 'FAILED'


class WebhookEvent(Enum):
    """WAHA Webhook Events"""
    MESSAGE = 'message'
    MESSAGE_ANY = 'message.any'
    MESSAGE_ACK = 'message.ack'
    MESSAGE_REACTION = 'message.reaction'
    STATE_CHANGE = 'state.change'
    GROUP_JOIN = 'group.join'
    GROUP_LEAVE = 'group.leave'
    PRESENCE_UPDATE = 'presence.update'
    POLL_VOTE = 'poll.vote'
    POLL_VOTE_FAILED = 'poll.vote.failed'
    CHAT_ARCHIVE = 'chat.archive'
    CALL_RECEIVED = 'call.received'
    CALL_ACCEPTED = 'call.accepted'
    CALL_REJECTED = 'call.rejected'


@dataclass
class WAHAConfig:
    """WAHA Configuration"""
    api_url: str
    api_key: str
    session: str = 'default'
    timeout: int = 30
    webhook_url: Optional[str] = None
    webhook_events: Optional[List[str]] = None


class WAHAService:
    """
    WAHA Service for comprehensive WhatsApp API management
    
    Features:
    - Session management (create, start, stop, restart, delete)
    - QR code authentication
    - Send various message types
    - Webhook configuration
    - Session status monitoring
    """

    def __init__(self, config: WAHAConfig):
        """
        Initialize WAHA Service
        
        Args:
            config: WAHAConfig with API credentials and settings
        """
        self.config = config
        self.api_url = config.api_url.rstrip('/')
        self.api_key = config.api_key
        self.session = config.session
        self.timeout = config.timeout

    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return {
            'Content-Type': 'application/json',
            'X-Api-Key': self.api_key,
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to WAHA API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            data: Request body data
            params: Query parameters
            
        Returns:
            Response data as dictionary
            
        Raises:
            WAHAAPIError: If request fails
        """
        url = f"{self.api_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Some endpoints return empty response
            if response.text:
                return response.json()
            return {'status': 'success'}
            
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', error_data.get('error', str(e)))
            except:
                pass
            _logger.error(f'WAHA API Error: {error_msg}')
            raise WAHAAPIError(error_msg)
        except requests.exceptions.RequestException as e:
            _logger.error(f'WAHA Request Error: {e}')
            raise WAHAAPIError(str(e))

    # ==================== Session Management ====================

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all WAHA sessions
        
        Endpoint: GET /api/sessions
        
        Returns:
            List of session objects
        """
        return self._make_request('GET', '/api/sessions')

    def create_session(self, session_name: Optional[str] = None, start: bool = True, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Create a new WAHA session
        
        Endpoint: POST /api/sessions
        
        Args:
            session_name: Session name (default: self.session)
            start: Start session immediately
            config: Additional session configuration
            
        Returns:
            Created session object
        """
        session_name = session_name or self.session
        
        payload = {
            'name': session_name,
            'start': start,
        }
        
        # Add webhook configuration if provided
        if self.config.webhook_url:
            payload['config'] = payload.get('config', {})
            payload['config']['webhooks'] = [{
                'url': self.config.webhook_url,
                'events': self.config.webhook_events or [
                    'message',
                    'message.ack',
                    'state.change',
                ],
            }]
        
        if config:
            payload['config'] = {**payload.get('config', {}), **config}
        
        return self._make_request('POST', '/api/sessions', data=payload)

    def get_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get session information
        
        Endpoint: GET /api/sessions/{session}
        
        Args:
            session_name: Session name
            
        Returns:
            Session object with status
        """
        session_name = session_name or self.session
        return self._make_request('GET', f'/api/sessions/{session_name}')

    def update_session(self, session_name: Optional[str] = None, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Update session configuration
        
        Endpoint: PUT /api/sessions/{session}
        
        Args:
            session_name: Session name
            config: New configuration
            
        Returns:
            Updated session object
        """
        session_name = session_name or self.session
        payload = {'config': config} if config else {}
        return self._make_request('PUT', f'/api/sessions/{session_name}', data=payload)

    def delete_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a session
        
        Endpoint: DELETE /api/sessions/{session}
        
        Args:
            session_name: Session name
            
        Returns:
            Deletion status
        """
        session_name = session_name or self.session
        return self._make_request('DELETE', f'/api/sessions/{session_name}')

    def start_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a session
        
        Endpoint: POST /api/sessions/{session}/start
        
        Args:
            session_name: Session name
            
        Returns:
            Session status
        """
        session_name = session_name or self.session
        return self._make_request('POST', f'/api/sessions/{session_name}/start')

    def stop_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Stop a session
        
        Endpoint: POST /api/sessions/{session}/stop
        
        Args:
            session_name: Session name
            
        Returns:
            Session status
        """
        session_name = session_name or self.session
        return self._make_request('POST', f'/api/sessions/{session_name}/stop')

    def restart_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Restart a session
        
        Endpoint: POST /api/sessions/{session}/restart
        
        Args:
            session_name: Session name
            
        Returns:
            Session status
        """
        session_name = session_name or self.session
        return self._make_request('POST', f'/api/sessions/{session_name}/restart')

    def logout_session(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Logout from session (disconnect WhatsApp)
        
        Endpoint: POST /api/sessions/{session}/logout
        
        Args:
            session_name: Session name
            
        Returns:
            Logout status
        """
        session_name = session_name or self.session
        return self._make_request('POST', f'/api/sessions/{session_name}/logout')

    def get_session_me(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get authenticated account information
        
        Endpoint: GET /api/sessions/{session}/me
        
        Args:
            session_name: Session name
            
        Returns:
            Account information (phone number, name, etc.)
        """
        session_name = session_name or self.session
        return self._make_request('GET', f'/api/sessions/{session_name}/me')

    # ==================== Authentication ====================

    def get_qr_code(self, session_name: Optional[str] = None, format: str = 'image') -> Dict[str, Any]:
        """
        Get QR code for WhatsApp pairing
        
        Endpoint: GET /api/{session}/auth/qr
        
        Args:
            session_name: Session name
            format: QR format ('image' or 'raw')
            
        Returns:
            QR code data (base64 image or raw value)
        """
        session_name = session_name or self.session
        params = {'format': format}
        return self._make_request('GET', f'/api/{session_name}/auth/qr', params=params)

    def request_auth_code(self, phone_number: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Request authentication code via phone number
        
        Endpoint: POST /api/{session}/auth/request-code
        
        Args:
            phone_number: Phone number to authenticate
            session_name: Session name
            
        Returns:
            Request status
        """
        session_name = session_name or self.session
        payload = {'phoneNumber': phone_number}
        return self._make_request('POST', f'/api/{session_name}/auth/request-code', data=payload)

    # ==================== Messaging ====================

    def send_text(self, chat_id: str, text: str, session_name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Send text message
        
        Endpoint: POST /api/sendText
        
        Args:
            chat_id: Chat ID (phone@c.us or group@g.us)
            text: Message text
            session_name: Session name
            **kwargs: Additional options (reply_to, mentions)
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'text': text,
            'session': session_name,
        }
        
        if kwargs.get('reply_to'):
            payload['reply_to'] = kwargs['reply_to']
        if kwargs.get('link_preview', True):
            payload['linkPreview'] = True
        
        return self._make_request('POST', '/api/sendText', data=payload)

    def send_image(self, chat_id: str, image_url: str, caption: str = '', session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send image message
        
        Endpoint: POST /api/sendImage
        
        Args:
            chat_id: Chat ID
            image_url: URL of the image
            caption: Optional caption
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'file': {'url': image_url},
            'caption': caption,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendImage', data=payload)

    def send_file(self, chat_id: str, file_url: str, filename: str = '', caption: str = '', session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send file/document
        
        Endpoint: POST /api/sendFile
        
        Args:
            chat_id: Chat ID
            file_url: URL of the file
            filename: Optional filename
            caption: Optional caption
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'file': {'url': file_url},
            'session': session_name,
        }
        
        if filename:
            payload['file']['filename'] = filename
        if caption:
            payload['caption'] = caption
        
        return self._make_request('POST', '/api/sendFile', data=payload)

    def send_voice(self, chat_id: str, voice_url: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send voice message
        
        Endpoint: POST /api/sendVoice
        
        Args:
            chat_id: Chat ID
            voice_url: URL of the voice file (OGG format preferred)
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'file': {'url': voice_url},
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendVoice', data=payload)

    def send_video(self, chat_id: str, video_url: str, caption: str = '', session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send video message
        
        Endpoint: POST /api/sendVideo
        
        Args:
            chat_id: Chat ID
            video_url: URL of the video
            caption: Optional caption
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'file': {'url': video_url},
            'caption': caption,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendVideo', data=payload)

    def send_location(self, chat_id: str, latitude: float, longitude: float, name: str = '', address: str = '', session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send location
        
        Endpoint: POST /api/sendLocation
        
        Args:
            chat_id: Chat ID
            latitude: Location latitude
            longitude: Location longitude
            name: Optional location name
            address: Optional location address
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'latitude': latitude,
            'longitude': longitude,
            'session': session_name,
        }
        
        if name:
            payload['name'] = name
        if address:
            payload['address'] = address
        
        return self._make_request('POST', '/api/sendLocation', data=payload)

    def send_contact_vcard(self, chat_id: str, vcard: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send contact vCard
        
        Endpoint: POST /api/sendContactVcard
        
        Args:
            chat_id: Chat ID
            vcard: vCard data string
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'vcard': vcard,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendContactVcard', data=payload)

    def send_poll(self, chat_id: str, name: str, options: List[str], multiple_answers: bool = False, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send poll
        
        Endpoint: POST /api/sendPoll
        
        Args:
            chat_id: Chat ID
            name: Poll question/name
            options: List of poll options
            multiple_answers: Allow multiple answers
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'name': name,
            'options': options,
            'multipleAnswers': multiple_answers,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendPoll', data=payload)

    def send_list(self, chat_id: str, title: str, description: str, button_text: str, sections: List[Dict], session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Send interactive list message
        
        Endpoint: POST /api/sendList
        
        Args:
            chat_id: Chat ID
            title: List title
            description: List description
            button_text: Button text
            sections: List sections with items
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'title': title,
            'description': description,
            'buttonText': button_text,
            'sections': sections,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendList', data=payload)

    def forward_message(self, chat_id: str, message_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Forward a message
        
        Endpoint: POST /api/forwardMessage
        
        Args:
            chat_id: Destination chat ID
            message_id: Message ID to forward
            session_name: Session name
            
        Returns:
            Message response with ID
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'messageId': message_id,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/forwardMessage', data=payload)

    # ==================== Chat Actions ====================

    def send_seen(self, chat_id: str, message_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Mark message as seen
        
        Endpoint: POST /api/sendSeen
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            session_name: Session name
            
        Returns:
            Status response
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'messageId': message_id,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/sendSeen', data=payload)

    def start_typing(self, chat_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Start typing indicator
        
        Endpoint: POST /api/startTyping
        
        Args:
            chat_id: Chat ID
            session_name: Session name
            
        Returns:
            Status response
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/startTyping', data=payload)

    def stop_typing(self, chat_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Stop typing indicator
        
        Endpoint: POST /api/stopTyping
        
        Args:
            chat_id: Chat ID
            session_name: Session name
            
        Returns:
            Status response
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'session': session_name,
        }
        
        return self._make_request('POST', '/api/stopTyping', data=payload)

    def react_to_message(self, chat_id: str, message_id: str, reaction: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        React to a message with emoji
        
        Endpoint: PUT /api/reaction
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            reaction: Emoji reaction (e.g., '👍', '❤️')
            session_name: Session name
            
        Returns:
            Status response
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'messageId': message_id,
            'reaction': reaction,
            'session': session_name,
        }
        
        return self._make_request('PUT', '/api/reaction', data=payload)

    def star_message(self, chat_id: str, message_id: str, star: bool = True, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Star or unstar a message
        
        Endpoint: PUT /api/star
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            star: True to star, False to unstar
            session_name: Session name
            
        Returns:
            Status response
        """
        session_name = session_name or self.session
        
        payload = {
            'chatId': chat_id,
            'messageId': message_id,
            'star': star,
            'session': session_name,
        }
        
        return self._make_request('PUT', '/api/star', data=payload)

    # ==================== Utility Methods ====================

    def format_phone_to_chat_id(self, phone: str) -> str:
        """
        Convert phone number to WAHA chat ID format
        
        Args:
            phone: Phone number (with or without +)
            
        Returns:
            Chat ID in format: {phone}@c.us
        """
        clean_phone = ''.join(filter(str.isdigit, phone))
        return f"{clean_phone}@c.us"

    def is_session_ready(self, session_name: Optional[str] = None) -> bool:
        """
        Check if session is ready for sending messages
        
        Args:
            session_name: Session name
            
        Returns:
            True if session is in WORKING state
        """
        try:
            session = self.get_session(session_name)
            status = session.get('status') or session.get('engine', {}).get('status')
            return status == SessionStatus.WORKING.value
        except:
            return False

    def ensure_session_ready(self, session_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Ensure session exists and is ready, create if needed
        
        Args:
            session_name: Session name
            
        Returns:
            Session status
        """
        session_name = session_name or self.session
        
        try:
            session = self.get_session(session_name)
            status = session.get('status') or session.get('engine', {}).get('status')
            
            if status == SessionStatus.STOPPED.value:
                return self.start_session(session_name)
            elif status == SessionStatus.WORKING.value:
                return session
            else:
                return session
                
        except WAHAAPIError:
            # Session doesn't exist, create it
            return self.create_session(session_name, start=True)


class WAHAAPIError(Exception):
    """Custom exception for WAHA API errors"""
    pass


# Convenience function to create service from config parameters
def create_waha_service(api_url: str, api_key: str, session: str = 'default', webhook_url: str = None, **kwargs) -> WAHAService:
    """
    Factory function to create WAHAService instance
    
    Args:
        api_url: WAHA API URL
        api_key: WAHA API key
        session: Session name
        webhook_url: Webhook URL for events
        **kwargs: Additional configuration
        
    Returns:
        Configured WAHAService instance
    """
    config = WAHAConfig(
        api_url=api_url,
        api_key=api_key,
        session=session,
        webhook_url=webhook_url,
        **kwargs
    )
    return WAHAService(config)


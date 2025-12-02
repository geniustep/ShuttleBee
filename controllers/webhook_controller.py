# -*- coding: utf-8 -*-
"""
Webhook controllers for receiving delivery status updates from notification providers
Includes support for:
- Generic SMS/WhatsApp webhooks
- WhatsApp Business API webhooks
- WAHA (WhatsApp HTTP API) webhooks
"""

import logging
import json
import hmac
import hashlib
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ShuttleBeeWebhookController(http.Controller):
    """Controller for webhook endpoints"""

    @http.route('/shuttlebee/webhook/notification/status', type='json', auth='public', methods=['POST'], csrf=False)
    def notification_status_webhook(self, **kwargs):
        """
        Webhook endpoint for notification delivery status updates

        Expected payload:
        {
            "provider_message_id": "msg_123456",
            "status": "delivered",  # or "failed", "read", etc.
            "error_message": "Optional error message",
            "timestamp": "2025-01-01T10:00:00Z"
        }

        Returns:
            dict: Status response
        """
        try:
            provider_message_id = kwargs.get('provider_message_id')
            status = kwargs.get('status')

            if not provider_message_id or not status:
                _logger.warning('Webhook received with missing parameters: %s', kwargs)
                return {'status': 'error', 'message': 'Missing required parameters'}

            # Update notification status
            notification_model = request.env['shuttle.notification'].sudo()
            result = notification_model.webhook_delivery_status(
                provider_message_id=provider_message_id,
                status=status,
                **kwargs
            )

            return result

        except Exception as e:
            _logger.error('Error processing notification webhook: %s', str(e), exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/shuttlebee/webhook/notification/status/sms', type='http', auth='public', methods=['POST'], csrf=False)
    def sms_status_webhook(self, **kwargs):
        """
        HTTP webhook endpoint for SMS provider status updates
        Some providers use HTTP POST with form data instead of JSON
        """
        try:
            # Try to parse JSON body first
            try:
                data = json.loads(request.httprequest.data)
            except:
                # Fallback to form data
                data = kwargs

            provider_message_id = data.get('message_id') or data.get('MessageSid')
            status = data.get('status') or data.get('MessageStatus')

            if not provider_message_id or not status:
                _logger.warning('SMS webhook received with missing parameters: %s', data)
                return Response('Missing required parameters', status=400)

            # Update notification status
            notification_model = request.env['shuttle.notification'].sudo()
            result = notification_model.webhook_delivery_status(
                provider_message_id=provider_message_id,
                status=status,
                **data
            )

            if result.get('status') == 'success':
                return Response('OK', status=200)
            else:
                return Response(result.get('message', 'Error'), status=400)

        except Exception as e:
            _logger.error('Error processing SMS webhook: %s', str(e), exc_info=True)
            return Response(str(e), status=500)

    @http.route('/shuttlebee/webhook/notification/status/whatsapp', type='http', auth='public', methods=['POST'], csrf=False)
    def whatsapp_status_webhook(self, **kwargs):
        """
        HTTP webhook endpoint for WhatsApp Business API status updates
        """
        try:
            # WhatsApp Business API sends JSON
            data = json.loads(request.httprequest.data)

            # WhatsApp Business API structure
            # https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            statuses = value.get('statuses', [])

            if not statuses:
                _logger.warning('WhatsApp webhook received with no statuses: %s', data)
                return Response('No statuses found', status=400)

            # Process each status update
            notification_model = request.env['shuttle.notification'].sudo()
            results = []

            for status_data in statuses:
                message_id = status_data.get('id')
                status = status_data.get('status')

                if message_id and status:
                    result = notification_model.webhook_delivery_status(
                        provider_message_id=message_id,
                        status=status,
                        timestamp=status_data.get('timestamp'),
                        error_message=status_data.get('errors', [{}])[0].get('message') if status_data.get('errors') else None
                    )
                    results.append(result)

            return Response('OK', status=200)

        except Exception as e:
            _logger.error('Error processing WhatsApp webhook: %s', str(e), exc_info=True)
            return Response(str(e), status=500)

    @http.route('/shuttlebee/webhook/health', type='http', auth='public', methods=['GET'], csrf=False)
    def webhook_health_check(self):
        """Health check endpoint for webhook monitoring"""
        return Response('ShuttleBee Webhook Service OK', status=200)

    # ==================== WAHA Webhooks ====================

    @http.route('/shuttlebee/webhook/waha', type='http', auth='public', methods=['POST'], csrf=False)
    def waha_webhook(self, **kwargs):
        """
        Main webhook endpoint for WAHA (WhatsApp HTTP API) events
        
        WAHA sends various events:
        - message: Incoming messages
        - message.any: All messages (including own)
        - message.ack: Message delivery acknowledgments
        - message.reaction: Message reactions
        - state.change: Session state changes
        - presence.update: Contact presence updates
        
        Expected payload structure:
        {
            "event": "message",
            "session": "default",
            "engine": "WEBJS",
            "payload": { ... event-specific data ... }
        }
        """
        try:
            # Parse JSON body
            try:
                data = json.loads(request.httprequest.data)
            except json.JSONDecodeError:
                _logger.warning('WAHA webhook received invalid JSON')
                return Response('Invalid JSON', status=400)
            
            event_type = data.get('event')
            session = data.get('session', 'default')
            payload = data.get('payload', {})
            
            _logger.info(f'WAHA webhook received: event={event_type}, session={session}')
            
            if not event_type:
                return Response('Missing event type', status=400)
            
            # Route to specific handler based on event type
            handlers = {
                'message': self._handle_waha_message,
                'message.any': self._handle_waha_message,
                'message.ack': self._handle_waha_message_ack,
                'message.reaction': self._handle_waha_message_reaction,
                'state.change': self._handle_waha_state_change,
                'presence.update': self._handle_waha_presence_update,
                'poll.vote': self._handle_waha_poll_vote,
                'call.received': self._handle_waha_call,
            }
            
            handler = handlers.get(event_type, self._handle_waha_unknown_event)
            result = handler(session, payload, data)
            
            return Response(json.dumps(result), status=200, content_type='application/json')
            
        except Exception as e:
            _logger.error(f'Error processing WAHA webhook: {e}', exc_info=True)
            return Response(str(e), status=500)

    def _handle_waha_message(self, session: str, payload: dict, full_data: dict) -> dict:
        """
        Handle incoming WAHA message event
        
        Payload structure:
        {
            "id": "message_id",
            "timestamp": 1234567890,
            "from": "1234567890@c.us",
            "to": "0987654321@c.us",
            "body": "Message text",
            "fromMe": false,
            "hasMedia": false,
            "ack": 0,
            ...
        }
        """
        message_id = payload.get('id')
        from_id = payload.get('from', '')
        to_id = payload.get('to', '')
        body = payload.get('body', '')
        from_me = payload.get('fromMe', False)
        has_media = payload.get('hasMedia', False)
        timestamp = payload.get('timestamp')
        
        _logger.info(f'WAHA message: id={message_id}, from={from_id}, fromMe={from_me}')
        
        # Skip messages sent by us
        if from_me:
            return {'status': 'success', 'message': 'Own message ignored'}
        
        # Extract phone number from chat ID (remove @c.us or @g.us suffix)
        phone_number = from_id.split('@')[0] if from_id else ''
        
        try:
            # Find partner by phone number
            partner = None
            if phone_number:
                partner = request.env['res.partner'].sudo().search([
                    '|',
                    ('phone', 'like', phone_number),
                    ('mobile', 'like', phone_number)
                ], limit=1)
            
            # Log the incoming message (you can extend this to create leads, tickets, etc.)
            _logger.info(f'WAHA incoming message from {phone_number}: {body[:100]}')
            
            # Optional: Create a mail.message for tracking
            if partner:
                # Log message in chatter
                partner.sudo().message_post(
                    body=f"📱 WhatsApp Message:\n{body}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
            
            return {
                'status': 'success',
                'message_id': message_id,
                'partner_id': partner.id if partner else None,
            }
            
        except Exception as e:
            _logger.error(f'Error handling WAHA message: {e}')
            return {'status': 'error', 'message': str(e)}

    def _handle_waha_message_ack(self, session: str, payload: dict, full_data: dict) -> dict:
        """
        Handle WAHA message acknowledgment event
        
        ACK levels:
        - 0: Pending (ACK_PENDING)
        - 1: Sent to server (ACK_SERVER)
        - 2: Received by device (ACK_DEVICE)
        - 3: Read (ACK_READ)
        - 4: Played (for audio/video)
        
        Payload structure:
        {
            "id": "message_id",
            "ack": 3,
            "ackName": "READ",
            ...
        }
        """
        message_id = payload.get('id')
        ack = payload.get('ack', 0)
        ack_name = payload.get('ackName', '')
        
        _logger.info(f'WAHA message ack: id={message_id}, ack={ack}, ackName={ack_name}')
        
        # Map WAHA ack to our status
        ack_status_map = {
            0: 'pending',
            1: 'sent',
            2: 'delivered',
            3: 'read',
            4: 'read',  # played = read for our purposes
        }
        
        status = ack_status_map.get(ack, 'sent')
        
        # Update notification status if we find the message
        try:
            notification_model = request.env['shuttle.notification'].sudo()
            result = notification_model.webhook_delivery_status(
                provider_message_id=message_id,
                status=status,
                ack=ack,
                ack_name=ack_name
            )
            return result
            
        except Exception as e:
            _logger.error(f'Error updating message ack status: {e}')
            return {'status': 'warning', 'message': f'Message not found: {message_id}'}

    def _handle_waha_message_reaction(self, session: str, payload: dict, full_data: dict) -> dict:
        """
        Handle WAHA message reaction event
        
        Payload structure:
        {
            "id": "reaction_id",
            "msgId": "message_id",
            "reaction": "👍",
            "from": "1234567890@c.us",
            ...
        }
        """
        reaction = payload.get('reaction', '')
        msg_id = payload.get('msgId', '')
        from_id = payload.get('from', '')
        
        _logger.info(f'WAHA reaction: msgId={msg_id}, reaction={reaction}, from={from_id}')
        
        return {
            'status': 'success',
            'message': 'Reaction received',
            'reaction': reaction,
        }

    def _handle_waha_state_change(self, session: str, payload: dict, full_data: dict) -> dict:
        """
        Handle WAHA session state change event
        
        States:
        - STOPPED
        - STARTING
        - SCAN_QR_CODE
        - WORKING
        - FAILED
        
        Payload structure:
        {
            "status": "WORKING"
        }
        """
        status = payload.get('status', '')
        
        _logger.info(f'WAHA state change: session={session}, status={status}')
        
        # You can add custom handling here, e.g., send notification to admins
        if status == 'SCAN_QR_CODE':
            _logger.warning(f'WAHA session {session} requires QR code scan!')
        elif status == 'FAILED':
            _logger.error(f'WAHA session {session} failed!')
        elif status == 'WORKING':
            _logger.info(f'WAHA session {session} is now working')
        
        return {
            'status': 'success',
            'session': session,
            'state': status,
        }

    def _handle_waha_presence_update(self, session: str, payload: dict, full_data: dict) -> dict:
        """
        Handle WAHA presence update event (online/offline/typing)
        
        Payload structure:
        {
            "id": "1234567890@c.us",
            "presences": [{"status": "online", "lastSeen": null}]
        }
        """
        chat_id = payload.get('id', '')
        presences = payload.get('presences', [])
        
        _logger.debug(f'WAHA presence update: id={chat_id}, presences={presences}')
        
        return {
            'status': 'success',
            'message': 'Presence update received',
        }

    def _handle_waha_poll_vote(self, session: str, payload: dict, full_data: dict) -> dict:
        """Handle WAHA poll vote event"""
        _logger.info(f'WAHA poll vote received: {payload}')
        return {'status': 'success', 'message': 'Poll vote received'}

    def _handle_waha_call(self, session: str, payload: dict, full_data: dict) -> dict:
        """Handle WAHA call event (received/accepted/rejected)"""
        _logger.info(f'WAHA call event received: {payload}')
        return {'status': 'success', 'message': 'Call event received'}

    def _handle_waha_unknown_event(self, session: str, payload: dict, full_data: dict) -> dict:
        """Handle unknown WAHA events"""
        event_type = full_data.get('event', 'unknown')
        _logger.warning(f'WAHA unknown event type: {event_type}')
        return {'status': 'success', 'message': f'Unknown event: {event_type}'}

    @http.route('/shuttlebee/webhook/waha/qr', type='http', auth='public', methods=['GET'], csrf=False)
    def waha_qr_proxy(self, **kwargs):
        """
        Proxy endpoint to get WAHA QR code
        This allows displaying the QR code in Odoo without exposing the API key
        
        Query params:
            session: Session name (default: 'default')
        """
        try:
            import requests
            
            # Get WAHA configuration
            params = request.env['ir.config_parameter'].sudo()
            api_url = params.get_param('shuttlebee.whatsapp_api_url')
            api_key = params.get_param('shuttlebee.whatsapp_api_key')
            session = kwargs.get('session', params.get_param('shuttlebee.waha_session', 'default'))
            
            if not api_url or not api_key:
                return Response('WAHA not configured', status=400)
            
            # Fetch QR code from WAHA
            response = requests.get(
                f"{api_url}/api/{session}/auth/qr",
                params={'format': 'image'},
                headers={'X-Api-Key': api_key},
                timeout=10
            )
            
            if response.status_code == 200:
                return Response(
                    response.content,
                    content_type=response.headers.get('Content-Type', 'image/png'),
                    status=200
                )
            else:
                return Response(f'QR code not available: {response.text}', status=response.status_code)
                
        except Exception as e:
            _logger.error(f'Error fetching WAHA QR code: {e}')
            return Response(str(e), status=500)

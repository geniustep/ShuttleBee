# -*- coding: utf-8 -*-
"""
Webhook controllers for receiving delivery status updates from notification providers
"""

import logging
import json
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

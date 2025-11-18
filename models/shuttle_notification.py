# -*- coding: utf-8 -*-

import logging
import re
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger('shuttlebee.notification')


class ShuttleNotification(models.Model):
    _name = 'shuttle.notification'
    _description = 'Shuttle Notification Log'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    # Relations
    trip_id = fields.Many2one(
        'shuttle.trip',
        string='Trip',
        ondelete='cascade',
        index=True
    )
    trip_line_id = fields.Many2one(
        'shuttle.trip.line',
        string='Trip Line',
        ondelete='cascade'
    )
    passenger_id = fields.Many2one(
        'res.partner',
        string='Passenger',
        required=True,
        index=True
    )

    # Notification Details
    notification_type = fields.Selection([
        ('approaching', 'Approaching'),
        ('arrived', 'Arrived at Stop'),
        ('trip_started', 'Trip Started'),
        ('trip_ended', 'Trip Ended'),
        ('cancelled', 'Trip Cancelled'),
        ('reminder', 'Reminder'),
        ('custom', 'Custom Message')
    ], string='Notification Type', required=True)

    channel = fields.Selection([
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('push', 'Push Notification'),
        ('email', 'Email')
    ], string='Channel', required=True, default='sms', index=True)

    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('read', 'Read')
    ], string='Status', default='pending', required=True, tracking=True, index=True)

    # Content
    message_content = fields.Text(
        string='Message Content',
        required=True
    )
    template_id = fields.Many2one(
        'mail.template',
        string='Template Used'
    )

    # Timestamps
    sent_date = fields.Datetime(
        string='Sent Date',
        readonly=True
    )
    delivered_date = fields.Datetime(
        string='Delivered Date',
        readonly=True
    )
    read_date = fields.Datetime(
        string='Read Date',
        readonly=True
    )

    # API Response
    api_response = fields.Text(
        string='API Response',
        readonly=True
    )
    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )

    # Phone/Email
    recipient_phone = fields.Char(string='Recipient Phone')
    recipient_email = fields.Char(string='Recipient Email')
    provider_message_id = fields.Char(
        string='Provider Message ID',
        copy=False,
        index=True
    )
    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        readonly=True
    )

    # Constraints
    @api.constrains('recipient_phone', 'channel')
    def _check_phone_required(self):
        """Validate phone number for SMS/WhatsApp channels"""
        for notification in self:
            if notification.channel in ['sms', 'whatsapp']:
                if not notification.recipient_phone:
                    raise ValidationError(_('Phone number is required for %s notifications!') % notification.channel.upper())
                if not self._is_valid_phone(notification.recipient_phone):
                    raise ValidationError(_('Invalid phone number format: %s') % notification.recipient_phone)

    @api.constrains('recipient_email', 'channel')
    def _check_email_required(self):
        """Validate email for email channel"""
        for notification in self:
            if notification.channel == 'email':
                email = notification.recipient_email or (notification.passenger_id and notification.passenger_id.email)
                if not email:
                    raise ValidationError(_('Email address is required for email notifications!'))
                if not self._is_valid_email(email):
                    raise ValidationError(_('Invalid email format: %s') % email)

    @api.model
    def _is_valid_phone(self, phone):
        """Validate phone number format (basic validation)"""
        if not phone:
            return False
        # Remove common separators
        phone_clean = re.sub(r'[\s\-\(\)\+]', '', phone)
        # Check if it contains only digits and is reasonable length (7-15 digits)
        return bool(re.match(r'^\d{7,15}$', phone_clean))

    @api.model
    def _is_valid_email(self, email):
        """Validate email format"""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    # Additional
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        compute='_compute_company',
        store=True,
        readonly=True,
        index=True
    )
    MAX_RETRIES = 3

    # Methods
    def _compute_company(self):
        for rec in self:
            rec.company_id = rec.trip_id.company_id or rec.passenger_id.company_id or rec.env.company

    def _mark_sent(self, extra_vals=None):
        vals = {
            'status': 'sent',
            'sent_date': fields.Datetime.now(),
            'error_message': False,
        }
        if extra_vals:
            vals.update(extra_vals)
        self.write(vals)

    def _mark_failed(self, message):
        self.write({
            'status': 'failed',
            'error_message': message,
            'retry_count': self.retry_count + 1,
        })

    def _get_company_param(self, key, default=None):
        company = self.company_id or self.env.company
        return self.env['res.config.settings']._get_company_param(self.env, key, company, default)

    def _send_notification(self):
        """Send the notification via the specified channel"""
        for notification in self:
            try:
                # Validate recipient information before sending
                if notification.channel in ['sms', 'whatsapp']:
                    if not notification.recipient_phone:
                        raise ValidationError(_('Phone number is required for %s notifications!') % notification.channel.upper())
                    if not self._is_valid_phone(notification.recipient_phone):
                        raise ValidationError(_('Invalid phone number format: %s') % notification.recipient_phone)
                
                elif notification.channel == 'email':
                    email = notification.recipient_email or (notification.passenger_id and notification.passenger_id.email)
                    if not email:
                        raise ValidationError(_('Email address is required for email notifications!'))
                    if not self._is_valid_email(email):
                        raise ValidationError(_('Invalid email format: %s') % email)

                channel_map = {
                    'sms': notification._send_sms,
                    'whatsapp': notification._send_whatsapp,
                    'push': notification._send_push,
                    'email': notification._send_email,
                }
                send_method = channel_map.get(notification.channel)
                if not send_method:
                    raise UserError(_('Unknown notification channel: %s') % notification.channel)

                response_vals = send_method() or {}
                notification._mark_sent(response_vals)
                _logger.info("Notification %s sent via %s", notification.id, notification.channel)

            except ValidationError:
                raise
            except Exception as e:
                error_msg = str(e)
                notification._mark_failed(error_msg)
                _logger.error(
                    "Failed to send notification %s via %s: %s",
                    notification.id,
                    notification.channel,
                    error_msg,
                    exc_info=True
                )

        return True

    def _send_sms(self):
        """Send SMS notification"""
        sms_api_url = self._get_company_param('shuttlebee.sms_api_url')
        sms_api_key = self._get_company_param('shuttlebee.sms_api_key')

        if not sms_api_url or not sms_api_key:
            _logger.warning(
                f'SMS API not configured for notification {self.id}. '
                'Please configure SMS API URL and Key in Settings.'
            )
            raise UserError(_('SMS API is not configured. Please configure it in Settings → ShuttleBee.'))

        if not self.recipient_phone:
            raise ValidationError(_('Recipient phone number is missing!'))

        try:
            # Clean phone number
            phone_clean = re.sub(r'[\s\-\(\)]', '', self.recipient_phone)
            if phone_clean.startswith('+'):
                phone_clean = phone_clean[1:]

            # Prepare request payload (adjust based on your SMS provider API)
            payload = {
                'to': phone_clean,
                'message': self.message_content,
                'api_key': sms_api_key
            }

            # Send SMS via API (example implementation)
            # Replace this with your actual SMS provider integration
            response = requests.post(
                sms_api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()

            return {
                'api_response': f'SMS sent successfully. Response: {response.text[:200]}',
                'provider_message_id': response.headers.get('X-Message-Id'),
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"SMS API request failed: {str(e)}"
            raise UserError(_('Failed to send SMS: %s') % str(e))
        except Exception as e:
            error_msg = f"Unexpected error sending SMS: {str(e)}"
            raise

    def _send_whatsapp(self):
        """Send WhatsApp notification via WhatsApp Business API"""
        whatsapp_api_url = self._get_company_param('shuttlebee.whatsapp_api_url')
        whatsapp_api_key = self._get_company_param('shuttlebee.whatsapp_api_key')

        if not whatsapp_api_url or not whatsapp_api_key:
            _logger.warning(
                f'WhatsApp API not configured for notification {self.id}. '
                'Please configure WhatsApp API URL and Key in Settings.'
            )
            raise UserError(_('WhatsApp API is not configured. Please configure it in Settings → ShuttleBee.'))

        if not self.recipient_phone:
            raise ValidationError(_('Recipient phone number is missing!'))

        try:
            # Clean phone number
            phone_clean = re.sub(r'[\s\-\(\)]', '', self.recipient_phone)
            if phone_clean.startswith('+'):
                phone_clean = phone_clean[1:]

            # Prepare request payload (adjust based on your WhatsApp provider API)
            payload = {
                'to': phone_clean,
                'message': self.message_content,
                'api_key': whatsapp_api_key
            }

            # Send WhatsApp message via API (example implementation)
            # Replace this with your actual WhatsApp provider integration
            response = requests.post(
                whatsapp_api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()

            return {
                'api_response': f'WhatsApp sent successfully. Response: {response.text[:200]}',
                'provider_message_id': response.headers.get('X-Message-Id'),
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"WhatsApp API request failed: {str(e)}"
            raise UserError(_('Failed to send WhatsApp: %s') % str(e))
        except Exception as e:
            error_msg = f"Unexpected error sending WhatsApp: {str(e)}"
            raise

    def _send_push(self):
        """Send push notification via Firebase Cloud Messaging or similar"""
        if not self.passenger_id:
            raise ValidationError(_('Passenger is required for push notifications!'))

        # Check if passenger has push token (you may need to add this field to res.partner)
        # For now, we'll log and mark as sent if no token is available
        push_token = getattr(self.passenger_id, 'push_notification_token', False)
        
        if not push_token:
            raise UserError(_('Passenger does not have a push notification token.'))

        try:
        # Integration with Firebase Cloud Messaging or similar
            # Replace this with your actual push notification service integration
            # Example FCM payload structure:
            payload = {
                'to': push_token,
                'notification': {
                    'title': 'ShuttleBee Notification',
                    'body': self.message_content,
                },
                'data': {
                    'trip_id': self.trip_id.id if self.trip_id else None,
                    'notification_type': self.notification_type,
                }
            }

            # Send push notification (implement based on your push service)
            # For FCM, you would use the Firebase Admin SDK or REST API
            _logger.info(f"Push notification prepared for passenger {self.passenger_id.id} in notification {self.id}")
            
            # Placeholder: Implement actual push sending logic here
            # response = fcm_service.send(payload)
            
            return {
                'api_response': 'Push notification sent successfully (implementation required)'
            }

        except Exception as e:
            error_msg = f"Unexpected error sending push notification: {str(e)}"
            raise UserError(_('Failed to send push notification: %s') % str(e))

    def _send_email(self):
        """Send email notification"""
        email = self.recipient_email or (self.passenger_id and self.passenger_id.email)
        
        if not email:
            raise ValidationError(_('Email address is required for email notifications!'))
        
        if not self._is_valid_email(email):
            raise ValidationError(_('Invalid email format: %s') % email)

        try:
            notification_type_label = dict(self._fields["notification_type"].selection).get(
                self.notification_type, self.notification_type
            )
            
            mail_values = {
                'subject': f'ShuttleBee: {notification_type_label}',
                'body_html': self.message_content,
                'email_to': email,
                'auto_delete': True,
            }
            
            # Add trip context if available
            if self.trip_id:
                mail_values['model'] = 'shuttle.trip'
                mail_values['res_id'] = self.trip_id.id

            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
            
            return {
                'api_response': f'Email sent successfully to {email}'
            }

        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            raise UserError(_('Failed to send email: %s') % str(e))

    def action_retry(self):
        """Retry sending failed notification"""
        for rec in self:
            if rec.retry_count >= self.MAX_RETRIES:
                raise UserError(_('Maximum retries exceeded for notification %s') % rec.display_name)
            rec.write({'status': 'pending', 'error_message': False})
            rec._send_notification()
        return True

    def action_mark_delivered(self):
        """Manually mark as delivered"""
        self.write({
            'status': 'delivered',
            'delivered_date': fields.Datetime.now()
        })
        return True

    def action_mark_read(self):
        """Manually mark as read"""
        self.write({
            'status': 'read',
            'read_date': fields.Datetime.now()
        })
        return True

    @api.model
    def get_recent_notifications(self, passenger_id=None, trip_id=None, limit=50):
        """Return recent notification logs for external consumers"""
        domain = []
        if passenger_id:
            domain.append(('passenger_id', '=', passenger_id))
        if trip_id:
            domain.append(('trip_id', '=', trip_id))

        notifications = self.search(domain, limit=limit, order='create_date desc')
        result = []
        for notif in notifications:
            result.append({
                'id': notif.id,
                'trip_id': notif.trip_id.id,
                'trip_line_id': notif.trip_line_id.id if notif.trip_line_id else False,
                'passenger_id': notif.passenger_id.id,
                'channel': notif.channel,
                'notification_type': notif.notification_type,
                'status': notif.status,
                'sent_date': notif.sent_date,
                'delivered_date': notif.delivered_date,
                'error_message': notif.error_message,
                'provider_message_id': notif.provider_message_id,
                'message_content': notif.message_content,
            })
        return result

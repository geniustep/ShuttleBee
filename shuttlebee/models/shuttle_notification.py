# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ShuttleNotification(models.Model):
    _name = 'shuttle.notification'
    _description = 'Shuttle Notification Log'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    # Relations
    trip_id = fields.Many2one(
        'shuttle.trip',
        string='Trip',
        required=True,
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
    ], string='Channel', required=True, default='sms')

    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('read', 'Read')
    ], string='Status', default='pending', required=True, tracking=True)

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

    # Additional
    company_id = fields.Many2one(
        related='trip_id.company_id',
        store=True,
        readonly=True
    )

    # Methods
    def _send_notification(self):
        """Send the notification via the specified channel"""
        for notification in self:
            try:
                if notification.channel == 'sms':
                    notification._send_sms()
                elif notification.channel == 'whatsapp':
                    notification._send_whatsapp()
                elif notification.channel == 'push':
                    notification._send_push()
                elif notification.channel == 'email':
                    notification._send_email()

                notification.write({
                    'status': 'sent',
                    'sent_date': fields.Datetime.now()
                })

            except Exception as e:
                notification.write({
                    'status': 'failed',
                    'error_message': str(e)
                })
                _logger.error(f"Failed to send notification {notification.id}: {str(e)}")

        return True

    def _send_sms(self):
        """Send SMS notification"""
        # Integration with SMS gateway (Twilio, etc.)
        # This is a placeholder - implement based on your SMS provider
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        sms_api_url = IrConfigParam.get_param('shuttlebee.sms_api_url')
        sms_api_key = IrConfigParam.get_param('shuttlebee.sms_api_key')

        if not sms_api_url or not sms_api_key:
            _logger.warning('SMS API not configured! Notification marked as sent for demo purposes.')
            self.write({'api_response': 'SMS API not configured (demo mode)'})
            return

        # Implement actual SMS sending logic here
        _logger.info(f"Sending SMS to {self.recipient_phone}: {self.message_content}")

        self.write({'api_response': 'SMS sent successfully (placeholder)'})

    def _send_whatsapp(self):
        """Send WhatsApp notification"""
        # Integration with WhatsApp Business API
        _logger.info(f"Sending WhatsApp to {self.recipient_phone}: {self.message_content}")
        self.write({'api_response': 'WhatsApp sent successfully (placeholder)'})

    def _send_push(self):
        """Send push notification"""
        # Integration with Firebase Cloud Messaging or similar
        _logger.info(f"Sending Push notification: {self.message_content}")
        self.write({'api_response': 'Push sent successfully (placeholder)'})

    def _send_email(self):
        """Send email notification"""
        try:
            mail_values = {
                'subject': f'ShuttleBee: {dict(self._fields["notification_type"].selection).get(self.notification_type)}',
                'body_html': self.message_content,
                'email_to': self.recipient_email or self.passenger_id.email,
            }
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
            self.write({'api_response': 'Email sent successfully'})
        except Exception as e:
            _logger.error(f"Failed to send email: {str(e)}")
            raise

    def action_retry(self):
        """Retry sending failed notification"""
        self.write({'status': 'pending', 'error_message': False})
        self._send_notification()
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

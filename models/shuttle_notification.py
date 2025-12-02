# -*- coding: utf-8 -*-

import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Import helper utilities
from ..helpers.validation import ValidationHelper
from ..helpers.retry_utils import retry_with_backoff, RetryConfig
from ..helpers.notification_providers import ProviderFactory
from ..helpers.logging_utils import StructuredLogger, notification_logger
from ..helpers.security_utils import template_renderer
from ..helpers.rate_limiter import notification_rate_limiter

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

    # Constraints using new ValidationHelper
    @api.constrains('recipient_phone', 'channel')
    def _check_phone_required(self):
        """Validate phone number for SMS/WhatsApp channels using ValidationHelper"""
        for notification in self:
            if notification.channel in ['sms', 'whatsapp']:
                try:
                    ValidationHelper.validate_contact_info(
                        channel=notification.channel,
                        phone=notification.recipient_phone,
                        raise_error=True
                    )
                except ValidationError:
                    # Re-raise with specific context
                    raise

    @api.constrains('recipient_email', 'channel')
    def _check_email_required(self):
        """Validate email for email channel using ValidationHelper"""
        for notification in self:
            if notification.channel == 'email':
                email = notification.recipient_email or (
                    notification.passenger_id and notification.passenger_id.email
                )
                try:
                    ValidationHelper.validate_contact_info(
                        channel='email',
                        email=email,
                        raise_error=True
                    )
                except ValidationError:
                    raise

    # Methods
    def _compute_company(self):
        for rec in self:
            rec.company_id = (
                rec.trip_id.company_id or
                rec.passenger_id.company_id or
                rec.env.company
            )

    def _mark_sent(self, extra_vals=None):
        """Mark notification as sent"""
        vals = {
            'status': 'sent',
            'sent_date': fields.Datetime.now(),
            'error_message': False,
        }
        if extra_vals:
            vals.update(extra_vals)
        self.write(vals)

        # Log success with structured logging
        notification_logger.info(
            'notification_sent',
            notification_id=self.id,
            channel=self.channel,
            notification_type=self.notification_type,
            passenger_id=self.passenger_id.id,
            trip_id=self.trip_id.id if self.trip_id else None
        )

    def _mark_failed(self, message):
        """Mark notification as failed"""
        self.write({
            'status': 'failed',
            'error_message': message,
            'retry_count': self.retry_count + 1,
        })

        # Log failure with structured logging
        notification_logger.error(
            'notification_failed',
            notification_id=self.id,
            channel=self.channel,
            notification_type=self.notification_type,
            error_message=message,
            retry_count=self.retry_count + 1
        )

    def _get_company_param(self, key, default=None):
        """Get company-specific parameter"""
        company = self.company_id or self.env.company
        return self.env['ir.config_parameter'].sudo().get_param(key, default)

    def _send_notification(self):
        """Send notification via specified channel with rate limiting and retries"""
        for notification in self:
            try:
                # Validate contact information before sending
                ValidationHelper.validate_contact_info(
                    channel=notification.channel,
                    phone=notification.recipient_phone,
                    email=notification.recipient_email or (
                        notification.passenger_id and notification.passenger_id.email
                    ),
                    raise_error=True
                )

                # Check rate limit
                if not notification_rate_limiter.is_allowed(notification.channel):
                    notification_logger.warning(
                        'rate_limit_exceeded',
                        notification_id=notification.id,
                        channel=notification.channel
                    )
                    raise UserError(
                        _('Rate limit exceeded for %s channel. Please try again later.') %
                        notification.channel.upper()
                    )

                # Map channel to send method
                channel_map = {
                    'sms': notification._send_sms,
                    'whatsapp': notification._send_whatsapp,
                    'push': notification._send_push,
                    'email': notification._send_email,
                }
                send_method = channel_map.get(notification.channel)

                if not send_method:
                    raise UserError(_('Unknown notification channel: %s') % notification.channel)

                # Send with retry logic
                response_vals = send_method() or {}
                notification._mark_sent(response_vals)

            except ValidationError:
                raise
            except Exception as e:
                error_msg = str(e)
                notification._mark_failed(error_msg)
                notification_logger.exception(
                    'notification_send_error',
                    notification_id=notification.id,
                    channel=notification.channel,
                    error=error_msg
                )

        return True

    @retry_with_backoff(
        max_retries=3,
        retry_on=(requests.exceptions.RequestException,),
        ignore_on=(ValidationError, UserError)
    )
    def _send_sms(self):
        """Send SMS notification using provider adapter with retry logic"""
        sms_api_url = self._get_company_param('shuttlebee.sms_api_url')
        sms_api_key = self._get_company_param('shuttlebee.sms_api_key')
        provider_type = self._get_company_param('shuttlebee.sms_provider_type', 'generic_sms')

        if not sms_api_url or not sms_api_key:
            notification_logger.warning(
                'sms_api_not_configured',
                notification_id=self.id
            )
            raise UserError(
                _('SMS API is not configured. Please configure it in Settings → ShuttleBee.')
            )

        # Clean phone number
        phone_clean = ValidationHelper.clean_phone(self.recipient_phone)

        try:
            # Create provider using factory
            provider = ProviderFactory.create_provider(
                provider_type=provider_type,
                api_url=sms_api_url,
                api_key=sms_api_key,
                timeout=10
            )

            # Send SMS
            result = provider.send(
                recipient=phone_clean,
                message=self.message_content
            )

            return {
                'api_response': result.get('api_response'),
                'provider_message_id': result.get('provider_message_id'),
            }

        except UserError:
            raise
        except Exception as e:
            notification_logger.error(
                'sms_send_failed',
                notification_id=self.id,
                phone=phone_clean,
                error=str(e)
            )
            raise UserError(_('Failed to send SMS: %s') % str(e))

    @retry_with_backoff(
        max_retries=3,
        retry_on=(requests.exceptions.RequestException,),
        ignore_on=(ValidationError, UserError)
    )
    def _send_whatsapp(self):
        """Send WhatsApp notification using provider adapter with retry logic"""
        whatsapp_api_url = self._get_company_param('shuttlebee.whatsapp_api_url')
        whatsapp_api_key = self._get_company_param('shuttlebee.whatsapp_api_key')
        provider_type = self._get_company_param('shuttlebee.whatsapp_provider_type', 'waha_whatsapp')

        if not whatsapp_api_url or not whatsapp_api_key:
            notification_logger.warning(
                'whatsapp_api_not_configured',
                notification_id=self.id
            )
            raise UserError(
                _('WhatsApp API is not configured. Please configure it in Settings → ShuttleBee.')
            )

        # Clean phone number
        phone_clean = ValidationHelper.clean_phone(self.recipient_phone)

        try:
            # Get provider-specific configuration
            extra_config = {}
            
            if provider_type == 'waha_whatsapp':
                # WAHA specific configuration
                waha_session = self._get_company_param('shuttlebee.waha_session', 'default')
                extra_config['session'] = waha_session
                extra_config['timeout'] = 30
            elif provider_type == 'whatsapp_business':
                # WhatsApp Business API configuration
                phone_number_id = self._get_company_param('shuttlebee.whatsapp_phone_number_id')
                extra_config['phone_number_id'] = phone_number_id

            # Create provider using factory
            provider = ProviderFactory.create_provider(
                provider_type=provider_type,
                api_url=whatsapp_api_url,
                api_key=whatsapp_api_key,
                **extra_config
            )

            # Send WhatsApp
            result = provider.send(
                recipient=phone_clean,
                message=self.message_content
            )

            notification_logger.info(
                'whatsapp_sent',
                notification_id=self.id,
                phone=phone_clean,
                provider=provider_type,
                message_id=result.get('provider_message_id')
            )

            return {
                'api_response': result.get('api_response'),
                'provider_message_id': result.get('provider_message_id'),
            }

        except UserError:
            raise
        except Exception as e:
            notification_logger.error(
                'whatsapp_send_failed',
                notification_id=self.id,
                phone=phone_clean,
                provider=provider_type,
                error=str(e)
            )
            raise UserError(_('Failed to send WhatsApp: %s') % str(e))

    def action_send_whatsapp_image(self, image_url, caption=''):
        """
        Send WhatsApp image message (WAHA specific feature)
        
        Args:
            image_url: URL of the image to send
            caption: Optional caption for the image
        """
        self.ensure_one()
        
        provider_type = self._get_company_param('shuttlebee.whatsapp_provider_type', 'waha_whatsapp')
        
        if provider_type != 'waha_whatsapp':
            raise UserError(_('Image sending is only supported with WAHA provider'))
        
        whatsapp_api_url = self._get_company_param('shuttlebee.whatsapp_api_url')
        whatsapp_api_key = self._get_company_param('shuttlebee.whatsapp_api_key')
        waha_session = self._get_company_param('shuttlebee.waha_session', 'default')
        
        phone_clean = ValidationHelper.clean_phone(self.recipient_phone)
        
        try:
            provider = ProviderFactory.create_provider(
                provider_type='waha_whatsapp',
                api_url=whatsapp_api_url,
                api_key=whatsapp_api_key,
                session=waha_session
            )
            
            result = provider.send_image(
                recipient=phone_clean,
                image_url=image_url,
                caption=caption
            )
            
            self._mark_sent({
                'api_response': result.get('api_response'),
                'provider_message_id': result.get('provider_message_id'),
            })
            
            return result
            
        except Exception as e:
            self._mark_failed(str(e))
            raise UserError(_('Failed to send WhatsApp image: %s') % str(e))

    def action_send_whatsapp_location(self, latitude, longitude, name='', address=''):
        """
        Send WhatsApp location message (WAHA specific feature)
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            name: Optional location name
            address: Optional address
        """
        self.ensure_one()
        
        provider_type = self._get_company_param('shuttlebee.whatsapp_provider_type', 'waha_whatsapp')
        
        if provider_type != 'waha_whatsapp':
            raise UserError(_('Location sending is only supported with WAHA provider'))
        
        whatsapp_api_url = self._get_company_param('shuttlebee.whatsapp_api_url')
        whatsapp_api_key = self._get_company_param('shuttlebee.whatsapp_api_key')
        waha_session = self._get_company_param('shuttlebee.waha_session', 'default')
        
        phone_clean = ValidationHelper.clean_phone(self.recipient_phone)
        
        try:
            provider = ProviderFactory.create_provider(
                provider_type='waha_whatsapp',
                api_url=whatsapp_api_url,
                api_key=whatsapp_api_key,
                session=waha_session
            )
            
            result = provider.send_location(
                recipient=phone_clean,
                latitude=latitude,
                longitude=longitude,
                name=name,
                address=address
            )
            
            self._mark_sent({
                'api_response': result.get('api_response'),
                'provider_message_id': result.get('provider_message_id'),
            })
            
            return result
            
        except Exception as e:
            self._mark_failed(str(e))
            raise UserError(_('Failed to send WhatsApp location: %s') % str(e))

    def _send_push(self):
        """Send push notification via Firebase Cloud Messaging"""
        if not self.passenger_id:
            raise ValidationError(_('Passenger is required for push notifications!'))

        # Get push token from passenger
        push_token = getattr(self.passenger_id, 'push_notification_token', False)

        if not push_token:
            raise UserError(_('Passenger does not have a push notification token.'))

        fcm_api_url = self._get_company_param('shuttlebee.fcm_api_url', 'https://fcm.googleapis.com')
        fcm_api_key = self._get_company_param('shuttlebee.fcm_api_key')

        if not fcm_api_key:
            notification_logger.warning(
                'fcm_api_not_configured',
                notification_id=self.id
            )
            raise UserError(
                _('Firebase Cloud Messaging is not configured. Please configure it in Settings → ShuttleBee.')
            )

        try:
            # Create FCM provider
            provider = ProviderFactory.create_provider(
                provider_type='firebase_push',
                api_url=fcm_api_url,
                api_key=fcm_api_key,
                timeout=10
            )

            # Send push notification
            result = provider.send(
                recipient=push_token,
                message=self.message_content,
                title='ShuttleBee Notification',
                notification_type=self.notification_type,
                trip_id=self.trip_id.id if self.trip_id else None
            )

            return {
                'api_response': result.get('api_response'),
                'provider_message_id': result.get('provider_message_id'),
            }

        except UserError:
            raise
        except Exception as e:
            notification_logger.error(
                'push_send_failed',
                notification_id=self.id,
                passenger_id=self.passenger_id.id,
                error=str(e)
            )
            raise UserError(_('Failed to send push notification: %s') % str(e))

    def _send_email(self):
        """Send email notification"""
        email = self.recipient_email or (self.passenger_id and self.passenger_id.email)

        if not email:
            raise ValidationError(_('Email address is required for email notifications!'))

        ValidationHelper.validate_email(email, raise_error=True)

        try:
            notification_type_label = dict(
                self._fields["notification_type"].selection
            ).get(self.notification_type, self.notification_type)

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

            notification_logger.info(
                'email_sent',
                notification_id=self.id,
                email=email,
                subject=mail_values['subject']
            )

            return {
                'api_response': f'Email sent successfully to {email}'
            }

        except Exception as e:
            notification_logger.error(
                'email_send_failed',
                notification_id=self.id,
                email=email,
                error=str(e)
            )
            raise UserError(_('Failed to send email: %s') % str(e))

    def action_retry(self):
        """Retry sending failed notification"""
        for rec in self:
            if rec.retry_count >= self.MAX_RETRIES:
                raise UserError(
                    _('Maximum retries exceeded for notification %s') % rec.display_name
                )
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

    @api.model
    def webhook_delivery_status(self, provider_message_id, status, **kwargs):
        """
        Webhook receiver for delivery status updates from SMS/WhatsApp providers

        Args:
            provider_message_id: Provider's message ID
            status: Delivery status (delivered, failed, read, etc.)
            **kwargs: Additional provider-specific data

        Returns:
            Dict with success status
        """
        notification = self.search([
            ('provider_message_id', '=', provider_message_id)
        ], limit=1)

        if not notification:
            notification_logger.warning(
                'webhook_notification_not_found',
                provider_message_id=provider_message_id
            )
            return {'status': 'error', 'message': 'Notification not found'}

        # Map provider status to our status
        status_map = {
            'delivered': 'delivered',
            'read': 'read',
            'failed': 'failed',
            'sent': 'sent',
        }

        mapped_status = status_map.get(status.lower(), 'sent')

        # Update notification status
        vals = {'status': mapped_status}

        if mapped_status == 'delivered':
            vals['delivered_date'] = fields.Datetime.now()
        elif mapped_status == 'read':
            vals['read_date'] = fields.Datetime.now()
        elif mapped_status == 'failed':
            vals['error_message'] = kwargs.get('error_message', 'Delivery failed')

        notification.write(vals)

        notification_logger.info(
            'webhook_status_updated',
            notification_id=notification.id,
            provider_message_id=provider_message_id,
            old_status=notification.status,
            new_status=mapped_status
        )

        return {'status': 'success', 'notification_id': notification.id}

# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Notification Settings
    shuttlebee_notification_channel = fields.Selection([
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('push', 'Push Notification'),
        ('email', 'Email')
    ], string='Default Notification Channel',
       config_parameter='shuttlebee.notification_channel',
       default='sms')

    # Timing Settings
    shuttlebee_approaching_minutes = fields.Integer(
        string='Send "Approaching" Notification (Minutes Before)',
        config_parameter='shuttlebee.approaching_minutes',
        default=10
    )
    shuttlebee_absent_timeout = fields.Integer(
        string='Mark Absent After (Minutes)',
        config_parameter='shuttlebee.absent_timeout',
        default=5
    )

    # Multi-company
    shuttlebee_company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    # API Settings
    shuttlebee_sms_api_url = fields.Char(
        string='SMS API URL',
        config_parameter='shuttlebee.sms_api_url'
    )
    shuttlebee_sms_api_key = fields.Char(
        string='SMS API Key',
        config_parameter='shuttlebee.sms_api_key'
    )
    
    # WhatsApp Provider Selection
    shuttlebee_whatsapp_provider_type = fields.Selection([
        ('waha_whatsapp', 'WAHA (WhatsApp HTTP API)'),
        ('whatsapp_business', 'WhatsApp Business API'),
        ('generic_whatsapp', 'Generic WhatsApp API'),
    ], string='WhatsApp Provider',
       config_parameter='shuttlebee.whatsapp_provider_type',
       default='waha_whatsapp')
    
    shuttlebee_whatsapp_api_url = fields.Char(
        string='WhatsApp API URL',
        config_parameter='shuttlebee.whatsapp_api_url',
        help='For WAHA: http://your-server:3000'
    )
    shuttlebee_whatsapp_api_key = fields.Char(
        string='WhatsApp API Key',
        config_parameter='shuttlebee.whatsapp_api_key',
        help='For WAHA: Your WAHA_API_KEY'
    )
    
    # WAHA Specific Settings
    shuttlebee_waha_session = fields.Char(
        string='WAHA Session Name',
        config_parameter='shuttlebee.waha_session',
        default='default',
        help='Name of the WAHA session to use'
    )
    shuttlebee_waha_webhook_url = fields.Char(
        string='WAHA Webhook URL',
        config_parameter='shuttlebee.waha_webhook_url',
        help='URL for WAHA to send webhook events (e.g., https://your-odoo.com/shuttlebee/webhook/waha)'
    )
    shuttlebee_waha_session_status = fields.Char(
        string='WAHA Session Status',
        compute='_compute_waha_session_status',
        readonly=True
    )

    # Message Templates
    shuttlebee_template_approaching = fields.Char(
        string='Approaching Message Template',
        config_parameter='shuttlebee.template_approaching',
        default='مرحباً {passenger_name}، السائق {driver_name} يقترب من نقطة التجمع {stop_name}. الوصول المتوقع: {eta} دقائق.'
    )
    shuttlebee_template_arrived = fields.Char(
        string='Arrived Message Template',
        config_parameter='shuttlebee.template_arrived',
        default='السائق {driver_name} وصل إلى {stop_name}. يرجى التوجه للحافلة.'
    )

    def set_values(self):
        super().set_values()
        company = self.shuttlebee_company_id or self.env.company
        company_id = company.id

        params = self.env['ir.config_parameter'].sudo()
        if company:
            suffix = f'.company_{company_id}'
        else:
            suffix = ''

        def _set_param(key, value):
            params.set_param(f'{key}{suffix}', value or '')

        _set_param('shuttlebee.notification_channel', self.shuttlebee_notification_channel)
        _set_param('shuttlebee.approaching_minutes', self.shuttlebee_approaching_minutes)
        _set_param('shuttlebee.absent_timeout', self.shuttlebee_absent_timeout)
        _set_param('shuttlebee.sms_api_url', self.shuttlebee_sms_api_url)
        _set_param('shuttlebee.sms_api_key', self.shuttlebee_sms_api_key)
        _set_param('shuttlebee.whatsapp_provider_type', self.shuttlebee_whatsapp_provider_type)
        _set_param('shuttlebee.whatsapp_api_url', self.shuttlebee_whatsapp_api_url)
        _set_param('shuttlebee.whatsapp_api_key', self.shuttlebee_whatsapp_api_key)
        _set_param('shuttlebee.waha_session', self.shuttlebee_waha_session)
        _set_param('shuttlebee.waha_webhook_url', self.shuttlebee_waha_webhook_url)
        _set_param('shuttlebee.template_approaching', self.shuttlebee_template_approaching)
        _set_param('shuttlebee.template_arrived', self.shuttlebee_template_arrived)

    @classmethod
    def _get_company_param(cls, env, key, company=None, default=False):
        company = company or env.company
        params = env['ir.config_parameter'].sudo()
        suffix = f'.company_{company.id}'
        value = params.get_param(f'{key}{suffix}')
        if value is None:
            value = params.get_param(key, default)
        return value

    @api.model
    def get_values(self):
        res = super().get_values()
        company = self.env.company
        res.update({
            'shuttlebee_company_id': company.id,
            'shuttlebee_notification_channel': self._get_company_param(self.env, 'shuttlebee.notification_channel', company, 'sms'),
            'shuttlebee_approaching_minutes': int(self._get_company_param(self.env, 'shuttlebee.approaching_minutes', company, 10)),
            'shuttlebee_absent_timeout': int(self._get_company_param(self.env, 'shuttlebee.absent_timeout', company, 5)),
            'shuttlebee_sms_api_url': self._get_company_param(self.env, 'shuttlebee.sms_api_url', company, ''),
            'shuttlebee_sms_api_key': self._get_company_param(self.env, 'shuttlebee.sms_api_key', company, ''),
            'shuttlebee_whatsapp_provider_type': self._get_company_param(self.env, 'shuttlebee.whatsapp_provider_type', company, 'waha_whatsapp'),
            'shuttlebee_whatsapp_api_url': self._get_company_param(self.env, 'shuttlebee.whatsapp_api_url', company, ''),
            'shuttlebee_whatsapp_api_key': self._get_company_param(self.env, 'shuttlebee.whatsapp_api_key', company, ''),
            'shuttlebee_waha_session': self._get_company_param(self.env, 'shuttlebee.waha_session', company, 'default'),
            'shuttlebee_waha_webhook_url': self._get_company_param(self.env, 'shuttlebee.waha_webhook_url', company, ''),
            'shuttlebee_template_approaching': self._get_company_param(self.env, 'shuttlebee.template_approaching', company, ''),
            'shuttlebee_template_arrived': self._get_company_param(self.env, 'shuttlebee.template_arrived', company, ''),
        })
        return res

    def _compute_waha_session_status(self):
        """Compute WAHA session status"""
        for record in self:
            record.shuttlebee_waha_session_status = 'غير مُهيأ'
            
            if not record.shuttlebee_whatsapp_api_url or not record.shuttlebee_whatsapp_api_key:
                continue
            
            if record.shuttlebee_whatsapp_provider_type != 'waha_whatsapp':
                record.shuttlebee_waha_session_status = 'غير مطبق (ليس WAHA)'
                continue
            
            try:
                from ..helpers.waha_service import create_waha_service, WAHAAPIError
                
                service = create_waha_service(
                    api_url=record.shuttlebee_whatsapp_api_url,
                    api_key=record.shuttlebee_whatsapp_api_key,
                    session=record.shuttlebee_waha_session or 'default'
                )
                
                session = service.get_session()
                status = session.get('status') or session.get('engine', {}).get('status', 'UNKNOWN')
                
                status_map = {
                    'WORKING': '✅ يعمل',
                    'STOPPED': '⏹️ متوقف',
                    'STARTING': '🔄 يبدأ...',
                    'SCAN_QR_CODE': '📱 يحتاج QR Code',
                    'FAILED': '❌ فشل',
                }
                record.shuttlebee_waha_session_status = status_map.get(status, f'❓ {status}')
                
            except Exception as e:
                _logger.warning(f'Failed to get WAHA session status: {e}')
                record.shuttlebee_waha_session_status = f'❌ خطأ: {str(e)[:50]}'

    def action_waha_create_session(self):
        """Create WAHA session"""
        self.ensure_one()
        
        if not self.shuttlebee_whatsapp_api_url or not self.shuttlebee_whatsapp_api_key:
            raise UserError(_('الرجاء إعداد WAHA API URL و API Key أولاً'))
        
        try:
            from ..helpers.waha_service import create_waha_service, WAHAAPIError
            
            service = create_waha_service(
                api_url=self.shuttlebee_whatsapp_api_url,
                api_key=self.shuttlebee_whatsapp_api_key,
                session=self.shuttlebee_waha_session or 'default',
                webhook_url=self.shuttlebee_waha_webhook_url
            )
            
            result = service.create_session()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WAHA Session'),
                    'message': _('تم إنشاء الجلسة بنجاح'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_('فشل إنشاء الجلسة: %s') % str(e))

    def action_waha_start_session(self):
        """Start WAHA session"""
        self.ensure_one()
        
        if not self.shuttlebee_whatsapp_api_url or not self.shuttlebee_whatsapp_api_key:
            raise UserError(_('الرجاء إعداد WAHA API URL و API Key أولاً'))
        
        try:
            from ..helpers.waha_service import create_waha_service
            
            service = create_waha_service(
                api_url=self.shuttlebee_whatsapp_api_url,
                api_key=self.shuttlebee_whatsapp_api_key,
                session=self.shuttlebee_waha_session or 'default'
            )
            
            result = service.start_session()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WAHA Session'),
                    'message': _('تم تشغيل الجلسة'),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_('فشل تشغيل الجلسة: %s') % str(e))

    def action_waha_stop_session(self):
        """Stop WAHA session"""
        self.ensure_one()
        
        if not self.shuttlebee_whatsapp_api_url or not self.shuttlebee_whatsapp_api_key:
            raise UserError(_('الرجاء إعداد WAHA API URL و API Key أولاً'))
        
        try:
            from ..helpers.waha_service import create_waha_service
            
            service = create_waha_service(
                api_url=self.shuttlebee_whatsapp_api_url,
                api_key=self.shuttlebee_whatsapp_api_key,
                session=self.shuttlebee_waha_session or 'default'
            )
            
            result = service.stop_session()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WAHA Session'),
                    'message': _('تم إيقاف الجلسة'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_('فشل إيقاف الجلسة: %s') % str(e))

    def action_waha_get_qr_code(self):
        """Get QR code for WAHA pairing"""
        self.ensure_one()
        
        if not self.shuttlebee_whatsapp_api_url or not self.shuttlebee_whatsapp_api_key:
            raise UserError(_('الرجاء إعداد WAHA API URL و API Key أولاً'))
        
        try:
            from ..helpers.waha_service import create_waha_service
            
            service = create_waha_service(
                api_url=self.shuttlebee_whatsapp_api_url,
                api_key=self.shuttlebee_whatsapp_api_key,
                session=self.shuttlebee_waha_session or 'default'
            )
            
            qr_data = service.get_qr_code(format='image')
            
            # Open wizard to display QR code
            return {
                'type': 'ir.actions.act_window',
                'name': _('WAHA QR Code'),
                'res_model': 'shuttle.waha.qr.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_qr_code_url': f"{self.shuttlebee_whatsapp_api_url}/api/{self.shuttlebee_waha_session or 'default'}/auth/qr?format=image",
                    'default_api_key': self.shuttlebee_whatsapp_api_key,
                }
            }
            
        except Exception as e:
            raise UserError(_('فشل الحصول على QR Code: %s') % str(e))

    def action_waha_test_connection(self):
        """Test WAHA API connection"""
        self.ensure_one()
        
        if not self.shuttlebee_whatsapp_api_url or not self.shuttlebee_whatsapp_api_key:
            raise UserError(_('الرجاء إعداد WAHA API URL و API Key أولاً'))
        
        try:
            from ..helpers.waha_service import create_waha_service
            
            service = create_waha_service(
                api_url=self.shuttlebee_whatsapp_api_url,
                api_key=self.shuttlebee_whatsapp_api_key,
                session=self.shuttlebee_waha_session or 'default'
            )
            
            sessions = service.list_sessions()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WAHA Connection'),
                    'message': _('✅ الاتصال ناجح! عدد الجلسات: %s') % len(sessions),
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_('❌ فشل الاتصال: %s') % str(e))

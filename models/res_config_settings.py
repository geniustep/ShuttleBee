# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
    shuttlebee_whatsapp_api_url = fields.Char(
        string='WhatsApp API URL',
        config_parameter='shuttlebee.whatsapp_api_url'
    )
    shuttlebee_whatsapp_api_key = fields.Char(
        string='WhatsApp API Key',
        config_parameter='shuttlebee.whatsapp_api_key'
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
        _set_param('shuttlebee.whatsapp_api_url', self.shuttlebee_whatsapp_api_url)
        _set_param('shuttlebee.whatsapp_api_key', self.shuttlebee_whatsapp_api_key)
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
            'shuttlebee_whatsapp_api_url': self._get_company_param(self.env, 'shuttlebee.whatsapp_api_url', company, ''),
            'shuttlebee_whatsapp_api_key': self._get_company_param(self.env, 'shuttlebee.whatsapp_api_key', company, ''),
            'shuttlebee_template_approaching': self._get_company_param(self.env, 'shuttlebee.template_approaching', company, ''),
            'shuttlebee_template_arrived': self._get_company_param(self.env, 'shuttlebee.template_arrived', company, ''),
        })
        return res

# -*- coding: utf-8 -*-

from odoo import fields, models


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
    shuttlebee_template_approaching = fields.Text(
        string='Approaching Message Template',
        config_parameter='shuttlebee.template_approaching',
        default='مرحباً {passenger_name}، السائق {driver_name} يقترب من نقطة التجمع {stop_name}. الوصول المتوقع: {eta} دقائق.'
    )
    shuttlebee_template_arrived = fields.Text(
        string='Arrived Message Template',
        config_parameter='shuttlebee.template_arrived',
        default='السائق {driver_name} وصل إلى {stop_name}. يرجى التوجه للحافلة.'
    )

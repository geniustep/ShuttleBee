# -*- coding: utf-8 -*-
"""
Shuttle Message Templates
Customizable message templates for all notification types
"""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ShuttleMessageTemplate(models.Model):
    _name = 'shuttle.message.template'
    _description = 'Shuttle Message Template'
    _order = 'notification_type, sequence'

    name = fields.Char(
        string='Template Name',
        required=True,
        translate=True
    )
    
    notification_type = fields.Selection([
        ('approaching', 'Approaching (السائق يقترب)'),
        ('arrived', 'Arrived (السائق وصل)'),
        ('trip_started', 'Trip Started (بدأت الرحلة)'),
        ('trip_ended', 'Trip Ended (انتهت الرحلة)'),
        ('cancelled', 'Trip Cancelled (ألغيت الرحلة)'),
        ('reminder', 'Reminder (تذكير)'),
        ('custom', 'Custom (مخصص)'),
    ], string='Notification Type', required=True, index=True)
    
    channel = fields.Selection([
        ('all', 'All Channels (جميع القنوات)'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('push', 'Push Notification'),
    ], string='Channel', default='all', required=True)
    
    language = fields.Selection([
        ('ar', 'Arabic (العربية)'),
        ('en', 'English'),
        ('fr', 'French (Français)'),
    ], string='Language', default='ar', required=True)
    
    subject = fields.Char(
        string='Subject (for Email)',
        translate=True,
        help='Subject line for email notifications'
    )
    
    body = fields.Text(
        string='Message Body',
        required=True,
        translate=True,
        help='''Available placeholders:
{passenger_name} - اسم الراكب
{driver_name} - اسم السائق
{vehicle_name} - اسم المركبة
{vehicle_plate} - لوحة المركبة
{stop_name} - اسم نقطة التوقف
{trip_name} - اسم الرحلة
{trip_date} - تاريخ الرحلة
{trip_time} - وقت الرحلة
{eta} - الوقت المتوقع للوصول
{company_name} - اسم الشركة
{company_phone} - هاتف الشركة
'''
    )
    
    body_html = fields.Html(
        string='HTML Body (for Email)',
        translate=True,
        help='Rich text version for email notifications'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True
    )
    
    is_default = fields.Boolean(
        string='Default Template',
        default=False,
        help='Use this template as default for this notification type'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True
    )
    
    # Preview
    preview_text = fields.Text(
        string='Preview',
        compute='_compute_preview',
        help='Preview of the message with sample data'
    )
    
    _sql_constraints = [
        ('unique_default_per_type_channel_lang',
         'UNIQUE(notification_type, channel, language, company_id, is_default)',
         'Only one default template per type/channel/language combination!')
    ]
    
    @api.depends('body')
    def _compute_preview(self):
        """Generate preview with sample data"""
        sample_data = {
            'passenger_name': 'أحمد محمد',
            'driver_name': 'خالد علي',
            'vehicle_name': 'حافلة 1',
            'vehicle_plate': 'أ ب ج 1234',
            'stop_name': 'محطة المدرسة',
            'trip_name': 'TRIP/2024/001',
            'trip_date': '2024-01-15',
            'trip_time': '07:30',
            'eta': '10',
            'company_name': 'شركة النقل',
            'company_phone': '+212 600 000 000',
        }
        
        for record in self:
            if record.body:
                try:
                    record.preview_text = record.body.format(**sample_data)
                except KeyError as e:
                    record.preview_text = f"خطأ في القالب: {e}"
                except Exception:
                    record.preview_text = record.body
            else:
                record.preview_text = ''
    
    @api.constrains('is_default', 'notification_type', 'channel', 'language', 'company_id')
    def _check_default_unique(self):
        """Ensure only one default template per type/channel/language"""
        for record in self:
            if record.is_default:
                existing = self.search([
                    ('id', '!=', record.id),
                    ('notification_type', '=', record.notification_type),
                    ('channel', 'in', [record.channel, 'all']),
                    ('language', '=', record.language),
                    ('company_id', '=', record.company_id.id),
                    ('is_default', '=', True),
                ])
                if existing:
                    raise ValidationError(_(
                        'A default template already exists for this type/channel/language combination: %s'
                    ) % existing[0].name)
    
    @api.model
    def get_template(self, notification_type, channel='all', language='ar', company=None):
        """
        Get the appropriate template for a notification
        
        Args:
            notification_type: Type of notification
            channel: Notification channel (sms, whatsapp, email, push)
            language: Language code (ar, en, fr)
            company: Company record (optional)
            
        Returns:
            shuttle.message.template record or False
        """
        company = company or self.env.company
        
        # First try to find exact match
        domain = [
            ('notification_type', '=', notification_type),
            ('channel', 'in', [channel, 'all']),
            ('language', '=', language),
            ('company_id', '=', company.id),
            ('is_active', '=', True),
        ]
        
        # Prefer default template
        template = self.search(domain + [('is_default', '=', True)], limit=1)
        if template:
            return template
        
        # Fallback to any active template
        template = self.search(domain, limit=1)
        if template:
            return template
        
        # Try without company restriction
        domain_no_company = [
            ('notification_type', '=', notification_type),
            ('channel', 'in', [channel, 'all']),
            ('language', '=', language),
            ('is_active', '=', True),
        ]
        template = self.search(domain_no_company + [('is_default', '=', True)], limit=1)
        if template:
            return template
        
        return self.search(domain_no_company, limit=1)
    
    def render_message(self, values):
        """
        Render the template with provided values
        
        Args:
            values: Dict with placeholder values
            
        Returns:
            Rendered message string
        """
        self.ensure_one()
        
        # Default empty values
        defaults = {
            'passenger_name': '',
            'driver_name': '',
            'vehicle_name': '',
            'vehicle_plate': '',
            'stop_name': '',
            'trip_name': '',
            'trip_date': '',
            'trip_time': '',
            'eta': '10',
            'company_name': self.company_id.name or self.env.company.name or '',
            'company_phone': self.company_id.phone or self.env.company.phone or '',
        }
        
        # Merge with provided values
        render_values = {**defaults, **values}
        
        try:
            return self.body.format(**render_values)
        except KeyError as e:
            _logger.warning(f'Missing placeholder in template {self.name}: {e}')
            return self.body
        except Exception as e:
            _logger.error(f'Error rendering template {self.name}: {e}')
            return self.body
    
    def action_set_as_default(self):
        """Set this template as default and unset others"""
        self.ensure_one()
        
        # Unset other defaults for same type/channel/language
        others = self.search([
            ('id', '!=', self.id),
            ('notification_type', '=', self.notification_type),
            ('channel', 'in', [self.channel, 'all']),
            ('language', '=', self.language),
            ('company_id', '=', self.company_id.id),
            ('is_default', '=', True),
        ])
        others.write({'is_default': False})
        
        # Set this as default
        self.is_default = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Default Template'),
                'message': _('تم تعيين هذا القالب كافتراضي'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_preview(self):
        """Open preview wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Preview Message'),
            'res_model': 'shuttle.message.template',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True},
        }
    
    @api.model
    def create_default_templates(self):
        """Create default templates for all notification types"""
        templates_data = [
            # Arabic Templates
            {
                'name': 'إشعار اقتراب السائق (عربي)',
                'notification_type': 'approaching',
                'language': 'ar',
                'channel': 'all',
                'is_default': True,
                'body': '''مرحباً {passenger_name} 👋

السائق {driver_name} يقترب من نقطة الالتقاط {stop_name}.

🚐 المركبة: {vehicle_name}
⏱️ الوقت المتوقع للوصول: {eta} دقائق

يرجى التجهز للصعود.

{company_name}
📞 {company_phone}''',
            },
            {
                'name': 'إشعار وصول السائق (عربي)',
                'notification_type': 'arrived',
                'language': 'ar',
                'channel': 'all',
                'is_default': True,
                'body': '''مرحباً {passenger_name} 👋

✅ السائق {driver_name} وصل إلى {stop_name}!

🚐 المركبة: {vehicle_name} ({vehicle_plate})

يرجى التوجه للمركبة فوراً.

{company_name}''',
            },
            {
                'name': 'إشعار بدء الرحلة (عربي)',
                'notification_type': 'trip_started',
                'language': 'ar',
                'channel': 'all',
                'is_default': True,
                'body': '''مرحباً {passenger_name} 👋

🚀 بدأت الرحلة {trip_name}!

👨‍✈️ السائق: {driver_name}
🚐 المركبة: {vehicle_name}
📅 التاريخ: {trip_date}

نتمنى لك رحلة آمنة!

{company_name}''',
            },
            {
                'name': 'إشعار إلغاء الرحلة (عربي)',
                'notification_type': 'cancelled',
                'language': 'ar',
                'channel': 'all',
                'is_default': True,
                'body': '''مرحباً {passenger_name} 👋

⚠️ تم إلغاء الرحلة {trip_name}

📅 التاريخ: {trip_date}

نعتذر عن أي إزعاج. يرجى التواصل معنا للمزيد من المعلومات.

{company_name}
📞 {company_phone}''',
            },
            {
                'name': 'تذكير بالرحلة (عربي)',
                'notification_type': 'reminder',
                'language': 'ar',
                'channel': 'all',
                'is_default': True,
                'body': '''مرحباً {passenger_name} 👋

🔔 تذكير: لديك رحلة قادمة!

📅 التاريخ: {trip_date}
⏰ الوقت: {trip_time}
📍 نقطة الالتقاط: {stop_name}
👨‍✈️ السائق: {driver_name}

يرجى التجهز في الوقت المحدد.

{company_name}''',
            },
            # English Templates
            {
                'name': 'Approaching Notification (English)',
                'notification_type': 'approaching',
                'language': 'en',
                'channel': 'all',
                'is_default': True,
                'body': '''Hello {passenger_name} 👋

Driver {driver_name} is approaching pickup point {stop_name}.

🚐 Vehicle: {vehicle_name}
⏱️ ETA: {eta} minutes

Please be ready for boarding.

{company_name}
📞 {company_phone}''',
            },
            {
                'name': 'Arrived Notification (English)',
                'notification_type': 'arrived',
                'language': 'en',
                'channel': 'all',
                'is_default': True,
                'body': '''Hello {passenger_name} 👋

✅ Driver {driver_name} has arrived at {stop_name}!

🚐 Vehicle: {vehicle_name} ({vehicle_plate})

Please head to the vehicle immediately.

{company_name}''',
            },
            {
                'name': 'Trip Started Notification (English)',
                'notification_type': 'trip_started',
                'language': 'en',
                'channel': 'all',
                'is_default': True,
                'body': '''Hello {passenger_name} 👋

🚀 Trip {trip_name} has started!

👨‍✈️ Driver: {driver_name}
🚐 Vehicle: {vehicle_name}
📅 Date: {trip_date}

Have a safe trip!

{company_name}''',
            },
            {
                'name': 'Trip Cancelled Notification (English)',
                'notification_type': 'cancelled',
                'language': 'en',
                'channel': 'all',
                'is_default': True,
                'body': '''Hello {passenger_name} 👋

⚠️ Trip {trip_name} has been cancelled.

📅 Date: {trip_date}

We apologize for any inconvenience. Please contact us for more information.

{company_name}
📞 {company_phone}''',
            },
        ]
        
        created = []
        for data in templates_data:
            existing = self.search([
                ('notification_type', '=', data['notification_type']),
                ('language', '=', data['language']),
                ('is_default', '=', True),
            ], limit=1)
            
            if not existing:
                template = self.create(data)
                created.append(template)
                _logger.info(f'Created default template: {data["name"]}')
        
        return created


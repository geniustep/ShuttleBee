# -*- coding: utf-8 -*-
"""
WAHA QR Code Wizard
Displays the QR code for WhatsApp authentication via WAHA
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShuttleWahaQrWizard(models.TransientModel):
    _name = 'shuttle.waha.qr.wizard'
    _description = 'WAHA QR Code Wizard'

    qr_code_url = fields.Char(
        string='QR Code URL',
        readonly=True
    )
    api_key = fields.Char(
        string='API Key',
        readonly=True
    )
    session_status = fields.Char(
        string='Session Status',
        compute='_compute_session_status'
    )
    instructions = fields.Html(
        string='Instructions',
        compute='_compute_instructions'
    )

    def _compute_session_status(self):
        """Check current session status"""
        for record in self:
            record.session_status = 'جاري التحقق...'
            
            try:
                params = self.env['ir.config_parameter'].sudo()
                api_url = params.get_param('shuttlebee.whatsapp_api_url')
                api_key = params.get_param('shuttlebee.whatsapp_api_key')
                session = params.get_param('shuttlebee.waha_session', 'default')
                
                if not api_url or not api_key:
                    record.session_status = '❌ WAHA غير مُهيأ'
                    continue
                
                from ..helpers.waha_service import create_waha_service, WAHAAPIError
                
                service = create_waha_service(
                    api_url=api_url,
                    api_key=api_key,
                    session=session
                )
                
                session_info = service.get_session()
                status = session_info.get('status') or session_info.get('engine', {}).get('status', 'UNKNOWN')
                
                status_map = {
                    'WORKING': '✅ متصل ويعمل',
                    'STOPPED': '⏹️ متوقف',
                    'STARTING': '🔄 يبدأ...',
                    'SCAN_QR_CODE': '📱 يحتاج مسح QR Code',
                    'FAILED': '❌ فشل الاتصال',
                }
                record.session_status = status_map.get(status, f'❓ {status}')
                
            except Exception as e:
                record.session_status = f'❌ خطأ: {str(e)[:30]}'

    def _compute_instructions(self):
        """Generate instructions HTML"""
        for record in self:
            record.instructions = """
            <div style="padding: 10px; background: #f8f9fa; border-radius: 8px;">
                <h4 style="color: #25D366;">🔗 خطوات ربط WhatsApp:</h4>
                <ol style="line-height: 2;">
                    <li>افتح تطبيق <strong>WhatsApp</strong> على هاتفك</li>
                    <li>اذهب إلى <strong>الإعدادات</strong> ← <strong>الأجهزة المرتبطة</strong></li>
                    <li>اضغط على <strong>"ربط جهاز"</strong></li>
                    <li>امسح رمز QR الظاهر في الأسفل</li>
                    <li>انتظر حتى يتم الاتصال</li>
                </ol>
                <p style="color: #666; font-size: 12px;">
                    <strong>ملاحظة:</strong> إذا لم يظهر رمز QR، اضغط على "تحديث QR Code"
                </p>
            </div>
            """

    def action_refresh_qr(self):
        """Refresh QR code"""
        self.ensure_one()
        
        try:
            params = self.env['ir.config_parameter'].sudo()
            api_url = params.get_param('shuttlebee.whatsapp_api_url')
            api_key = params.get_param('shuttlebee.whatsapp_api_key')
            session = params.get_param('shuttlebee.waha_session', 'default')
            
            # Update the QR URL with timestamp to prevent caching
            import time
            self.qr_code_url = f"{api_url}/api/{session}/auth/qr?format=image&t={int(time.time())}"
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('QR Code'),
                    'message': _('تم تحديث رمز QR'),
                    'type': 'info',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(_('فشل تحديث QR Code: %s') % str(e))

    def action_check_status(self):
        """Check session status"""
        self.ensure_one()
        
        # Recompute status
        self._compute_session_status()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Session Status'),
                'message': self.session_status,
                'type': 'info',
                'sticky': False,
            }
        }


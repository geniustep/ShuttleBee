# -*- coding: utf-8 -*-

import uuid

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Shuttle Passenger Info
    is_shuttle_passenger = fields.Boolean(
        string='Is Shuttle Passenger',
        default=False
    )

    # Default Stops
    default_pickup_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Default Pickup Stop',
        domain=[('stop_type', 'in', ['pickup', 'both'])]
    )
    default_dropoff_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Default Dropoff Stop',
        domain=[('stop_type', 'in', ['dropoff', 'both'])]
    )

    # Trip History
    shuttle_trip_line_ids = fields.One2many(
        'shuttle.trip.line',
        'passenger_id',
        string='Trip History'
    )

    # Statistics
    total_trips = fields.Integer(
        string='Total Trips',
        compute='_compute_shuttle_stats',
        store=True
    )
    present_trips = fields.Integer(
        string='Present Count',
        compute='_compute_shuttle_stats',
        store=True
    )
    absent_trips = fields.Integer(
        string='Absent Count',
        compute='_compute_shuttle_stats',
        store=True
    )
    attendance_rate = fields.Float(
        string='Attendance Rate (%)',
        compute='_compute_shuttle_stats',
        store=True
    )

    # Notes
    shuttle_notes = fields.Text(
        string='Shuttle Notes',
        help='Special requirements or notes for transportation'
    )

    # GPS Coordinates (for passengers without assigned stops)
    shuttle_latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        help='GPS latitude for custom pickup location'
    )
    shuttle_longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        help='GPS longitude for custom pickup location'
    )
    guardian_id = fields.Many2one(
        'res.partner',
        string='Guardian / Parent',
        help='Primary guardian responsible for this passenger.'
    )
    guardian_phone = fields.Char(
        string='Guardian Phone'
    )
    guardian_email = fields.Char(
        string='Guardian Email'
    )
    portal_access_token = fields.Char(
        string='Portal Access Token',
        copy=False
    )

    # Computed Methods
    @api.depends('shuttle_trip_line_ids.status')
    def _compute_shuttle_stats(self):
        for partner in self:
            lines = partner.shuttle_trip_line_ids
            partner.total_trips = len(lines)
            partner.present_trips = len(lines.filtered(
                lambda l: l.status in ['boarded', 'dropped']))
            partner.absent_trips = len(lines.filtered(
                lambda l: l.status == 'absent'))

            if partner.total_trips > 0:
                partner.attendance_rate = (partner.present_trips / partner.total_trips) * 100
            else:
                partner.attendance_rate = 0.0

    def action_view_shuttle_trips(self):
        """View shuttle trips for this passenger"""
        self.ensure_one()
        return {
            'name': _('Shuttle Trips'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.trip.line',
            'view_mode': 'list,form',
            'domain': [('passenger_id', '=', self.id)],
            'context': {'default_passenger_id': self.id}
        }

    def _ensure_portal_token(self):
        for partner in self:
            if not partner.portal_access_token:
                partner.portal_access_token = uuid.uuid4().hex

    def action_send_portal_invitation(self):
        """Prepare to send a portal invitation email to the guardian"""
        for partner in self:
            if not partner.guardian_email:
                raise ValidationError(
                    _('Please set a guardian email before sending an invitation.')
                )
            partner._ensure_portal_token()
            body = _(
                'Hello %(guardian)s,<br/><br/>'
                'You can access the ShuttleBee portal to follow %(student)s using the following token: <b>%(token)s</b>.<br/>'
                'A dedicated portal interface will be available soon.<br/><br/>'
                'Best regards,<br/>ShuttleBee'
            ) % {
                'guardian': partner.guardian_id.name or partner.guardian_email,
                'student': partner.name,
                'token': partner.portal_access_token,
            }
            mail_values = {
                'subject': _('ShuttleBee Portal Invitation'),
                'body_html': body,
                'email_to': partner.guardian_email,
                'email_from': partner.company_id.email or self.env.user.email or 'noreply@example.com',
            }
            self.env['mail.mail'].create(mail_values).send()

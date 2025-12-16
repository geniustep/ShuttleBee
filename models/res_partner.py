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
    # Auto Notification Info
    is_auto_notification = fields.Boolean(
        string='Auto Notification',
        default=True
    )
    
    # Default Stops
    use_gps_for_pickup = fields.Boolean(
        string='Use GPS Coordinates for Pickup',
        default=True,
        help='If enabled, GPS coordinates will be used as default pickup location instead of a stop. You can still override with a specific stop.'
    )
    default_pickup_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Default Pickup Stop (Override)',
        domain=[('stop_type', 'in', ['pickup', 'both'])],
        help='Optional: Override GPS coordinates with a specific stop. Leave empty to use GPS coordinates.'
    )
    use_gps_for_dropoff = fields.Boolean(
        string='Use Company GPS Coordinates for Dropoff',
        default=True,
        help='If enabled, company GPS coordinates will be used as default dropoff location. You can override with a specific stop if disabled.'
    )
    shuttle_trip_direction = fields.Selection([
        ('both', 'Pickup & Dropoff'),
        ('pickup', 'Pickup Only'),
        ('dropoff', 'Dropoff Only'),
    ], string='Trip Direction Preference', default='both',
       help='Define whether this passenger uses both pickup and dropoff trips or only one direction.')
    default_dropoff_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Default Dropoff Stop (Override)',
        domain=[('stop_type', 'in', ['dropoff', 'both'])],
        help='Required if GPS coordinates are not used. Override company GPS coordinates with a specific stop.'
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
    has_guardian = fields.Boolean(
        string='Has Guardian',
        default=False,
        help='Enable if this passenger has a guardian'
    )
    father_name = fields.Char(
        string='Father Name',
        help='Name of the father'
    )
    father_phone = fields.Char(
        string='Father Phone',
        help='Phone number of the father'
    )
    mother_name = fields.Char(
        string='Mother Name',
        help='Name of the mother'
    )
    mother_phone = fields.Char(
        string='Mother Phone',
        help='Phone number of the mother'
    )
    
    # Temporary/Secondary Address
    temporary_address = fields.Text(
        string='Temporary/Secondary Address',
        help='Temporary or secondary address for this passenger'
    )
    temporary_latitude = fields.Float(
        string='Temporary Latitude',
        digits=(10, 7),
        help='GPS latitude for temporary/secondary location'
    )
    temporary_longitude = fields.Float(
        string='Temporary Longitude',
        digits=(10, 7),
        help='GPS longitude for temporary/secondary location'
    )
    temporary_contact_name = fields.Char(
        string='Temporary Address Contact Name',
        help='Name of contact person related to this temporary/secondary address'
    )
    temporary_contact_phone = fields.Char(
        string='Temporary Address Contact Phone',
        help='Phone number of contact person related to this temporary/secondary address'
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
        """Prepare to send a portal invitation to the guardian (via SMS/WhatsApp)"""
        for partner in self:
            # Get guardian information (prefer father, then mother)
            guardian_name = None
            guardian_phone = None
            
            if partner.father_phone:
                guardian_name = partner.father_name or _('Father')
                guardian_phone = partner.father_phone
            elif partner.mother_phone:
                guardian_name = partner.mother_name or _('Mother')
                guardian_phone = partner.mother_phone
            
            if not guardian_phone:
                raise ValidationError(
                    _('Please set guardian phone number (father or mother) before sending an invitation.')
                )
            
            partner._ensure_portal_token()
            # Note: This function can be extended to send SMS/WhatsApp instead of email
            # For now, it generates the token but requires email integration for actual sending
            raise ValidationError(
                _('Portal invitation via SMS/WhatsApp will be available soon. Token generated: %s') % partner.portal_access_token
            )

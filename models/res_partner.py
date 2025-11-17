# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


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

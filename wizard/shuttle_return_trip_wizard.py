# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShuttleReturnTripWizard(models.TransientModel):
    _name = 'shuttle.return.trip.wizard'
    _description = 'Create Return Trip Wizard'

    trip_id = fields.Many2one(
        'shuttle.trip',
        string='Original Trip',
        required=True,
        readonly=True
    )
    return_trip_start_time = fields.Datetime(
        string='Return Trip Start Time',
        required=True
    )
    return_trip_arrival_time = fields.Datetime(
        string='Return Trip Arrival Time'
    )

    def action_create_return_trip(self):
        self.ensure_one()
        if not self.trip_id:
            raise UserError(_('Please select a trip.'))

        return_trip = self.trip_id.create_return_trip(
            start_time=self.return_trip_start_time,
            arrival_time=self.return_trip_arrival_time
        )

        return {
            'name': _('Return Trip'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.trip',
            'view_mode': 'form',
            'res_id': return_trip.id,
            'target': 'current',
        }

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShuttleTripWizard(models.TransientModel):
    _name = 'shuttle.trip.wizard'
    _description = 'Generate Trips from Passenger Group'

    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Passenger Group',
        required=True
    )
    trip_date = fields.Date(
        string='Trip Date',
        required=True,
        default=fields.Date.context_today
    )
    create_pickup_trip = fields.Boolean(
        string='Create Pickup Trip',
        default=True
    )
    create_dropoff_trip = fields.Boolean(
        string='Create Dropoff Trip',
        default=False
    )
    pickup_start_time = fields.Datetime(string='Pickup Start Time')
    pickup_arrival_time = fields.Datetime(string='Pickup Arrival Time')
    dropoff_start_time = fields.Datetime(string='Dropoff Start Time')
    dropoff_arrival_time = fields.Datetime(string='Dropoff Arrival Time')
    driver_id = fields.Many2one('res.users', string='Driver')
    vehicle_id = fields.Many2one('shuttle.vehicle', string='Vehicle')
    total_seats = fields.Integer(string='Seat Capacity')
    notes = fields.Text(string='Trip Notes')

    def action_generate_trips(self):
        self.ensure_one()
        if not self.group_id:
            raise UserError(_('Please select a passenger group.'))

        created_trips = self.env['shuttle.trip']
        if self.create_pickup_trip:
            if not self.pickup_start_time:
                raise UserError(_('Please set a start time for the pickup trip.'))
            created_trips += self._create_trip(
                trip_type='pickup',
                start_time=self.pickup_start_time,
                arrival_time=self.pickup_arrival_time,
            )

        if self.create_dropoff_trip:
            if not self.dropoff_start_time:
                raise UserError(_('Please set a start time for the dropoff trip.'))
            created_trips += self._create_trip(
                trip_type='dropoff',
                start_time=self.dropoff_start_time,
                arrival_time=self.dropoff_arrival_time,
            )

        if not created_trips:
            raise UserError(_('Select at least one trip to generate.'))

        action = self.env['ir.actions.act_window']._for_xml_id('shuttlebee.action_shuttle_trip')
        action['domain'] = [('id', 'in', created_trips.ids)]
        return action

    def _create_trip(self, trip_type, start_time, arrival_time):
        self.ensure_one()
        group = self.group_id
        vehicle = self.vehicle_id or group.vehicle_id
        total_seats = self.total_seats or group.total_seats or (vehicle.seat_capacity if vehicle else 0)
        seat_required = sum(group.line_ids.mapped('seat_count'))
        if total_seats and seat_required > total_seats:
            raise UserError(_(
                'Passenger seats (%s) exceed selected capacity (%s).'
            ) % (seat_required, total_seats))

        vals = {
            'name': '%s - %s' % (group.name, trip_type.title()),
            'trip_type': trip_type,
            'date': self.trip_date,
            'planned_start_time': start_time,
            'planned_arrival_time': arrival_time,
            'driver_id': self.driver_id.id or group.driver_id.id or (vehicle.driver_id.id if vehicle and vehicle.driver_id else False),
            'vehicle_id': vehicle.id if vehicle else False,
            'total_seats': total_seats,
            'notes': self.notes or group.notes,
            'group_id': group.id,
        }

        trip = self.env['shuttle.trip'].create(vals)

        line_vals = group._prepare_trip_line_values(trip.id, trip_type)
        self.env['shuttle.trip.line'].create(line_vals)

        # Link stops to the trip for quick reference
        stop_ids = set()
        for line in group.line_ids:
            if trip_type == 'pickup' and line.pickup_stop_id:
                stop_ids.add(line.pickup_stop_id.id)
            if trip_type == 'dropoff' and line.dropoff_stop_id:
                stop_ids.add(line.dropoff_stop_id.id)
        if stop_ids:
            trip.stop_ids = [(6, 0, list(stop_ids))]

        return trip

# -*- coding: utf-8 -*-

import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShuttlePassengerGroup(models.Model):
    _name = 'shuttle.passenger.group'
    _description = 'Passenger Group / Route Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Group Name', required=True, tracking=True, translate=True)
    code = fields.Char(string='Reference', copy=False)
    driver_id = fields.Many2one(
        'res.users',
        string='Default Driver',
        tracking=True
    )
    vehicle_id = fields.Many2one(
        'shuttle.vehicle',
        string='Vehicle',
        help='Vehicle typically assigned to this group/route.'
    )
    total_seats = fields.Integer(
        string='Seat Capacity',
        default=15,
        tracking=True
    )
    trip_type = fields.Selection([
        ('pickup', 'Pickup (Home ➜ School)'),
        ('dropoff', 'Dropoff (School ➜ Home)'),
        ('both', 'Pickup & Dropoff'),
    ], string='Default Trip Type', default='both', required=True)
    destination_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Destination Stop (School/Work)',
        domain=[('stop_type', 'in', ['dropoff', 'both'])],
        help='Common destination for all passengers (e.g., School, Office). '
             'Will be used as dropoff stop for pickup trips and pickup stop for dropoff trips.'
    )
    color = fields.Integer(string='Color Index')
    notes = fields.Text(string='Notes', translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True
    )

    line_ids = fields.One2many(
        'shuttle.passenger.group.line',
        'group_id',
        string='Passengers'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True
    )
    subscription_price = fields.Monetary(
        string='Subscription Price',
        currency_field='currency_id',
        help='Default price for this passenger group (monthly or per trip).'
    )
    billing_cycle = fields.Selection([
        ('per_trip', 'Per Trip'),
        ('monthly', 'Monthly'),
        ('per_term', 'Per Term/Semester'),
    ], string='Billing Cycle', default='monthly')
    member_count = fields.Integer(
        string='Passenger Count',
        compute='_compute_member_count',
        store=True
    )
    passenger_count = fields.Integer(
        string='Passenger Count (Cached)',
        compute='_compute_member_count',
        store=True
    )

    _sql_constraints = [
        ('positive_capacity', 'CHECK(total_seats > 0)',
         'Seat capacity must be positive.'),
    ]

    @api.depends('line_ids')
    def _compute_member_count(self):
        for group in self:
            total = len(group.line_ids)
            group.member_count = total
            group.passenger_count = total

    def action_open_generate_trip_wizard(self):
        self.ensure_one()
        return {
            'name': _('Generate Trip'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.trip.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_group_id': self.id,
                'default_driver_id': self.driver_id.id,
                'default_vehicle_id': self.vehicle_id.id,
                'default_total_seats': self.total_seats,
                'default_create_pickup_trip': True,
                'default_create_dropoff_trip': self.trip_type == 'both',
            }
        }

    def action_open_related_trips(self):
        self.ensure_one()
        return {
            'name': _('Trips'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.trip',
            'view_mode': 'list,kanban,form,calendar',
            'domain': [('group_id', '=', self.id)],
            'context': {
                'default_group_id': self.id,
                'default_driver_id': self.driver_id.id,
                'default_total_seats': self.total_seats,
            }
        }

    def _prepare_trip_line_values(self, trip_id=None, trip_type=None):
        self.ensure_one()
        if not self.line_ids:
            return []

        line_vals = []
        for line in self.line_ids:
            if not line.passenger_id:
                continue
            
            passenger = line.passenger_id
            vals = {
                'group_line_id': line.id,
                'passenger_id': passenger.id,
                'pickup_stop_id': line.pickup_stop_id.id if line.pickup_stop_id else False,
                'dropoff_stop_id': line.dropoff_stop_id.id if line.dropoff_stop_id else False,
                'seat_count': line.seat_count or 1,
                'notes': line.notes,
            }
            
            # Use destination_stop_id if passenger doesn't have a stop for the trip direction
            if trip_type == 'pickup':
                # For pickup trips: destination is dropoff (school/work)
                if not vals['dropoff_stop_id'] and self.destination_stop_id:
                    vals['dropoff_stop_id'] = self.destination_stop_id.id
            elif trip_type == 'dropoff':
                # For dropoff trips: destination is pickup (school/work)
                if not vals['pickup_stop_id'] and self.destination_stop_id:
                    vals['pickup_stop_id'] = self.destination_stop_id.id
            
            # Only add trip_id if provided (for actual creation, not onchange)
            if trip_id:
                vals['trip_id'] = trip_id
            
            # If no pickup stop but passenger has coordinates, use them
            if not vals['pickup_stop_id'] and passenger.shuttle_latitude and passenger.shuttle_longitude:
                vals['pickup_latitude'] = passenger.shuttle_latitude
                vals['pickup_longitude'] = passenger.shuttle_longitude
            
            # If no dropoff stop but passenger has coordinates, use them
            if not vals['dropoff_stop_id'] and passenger.shuttle_latitude and passenger.shuttle_longitude:
                vals['dropoff_latitude'] = passenger.shuttle_latitude
                vals['dropoff_longitude'] = passenger.shuttle_longitude
            
            line_vals.append(vals)
        return line_vals


class ShuttlePassengerGroupLine(models.Model):
    _name = 'shuttle.passenger.group.line'
    _description = 'Passenger Group Member'
    _order = 'sequence, id'

    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Group',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(default=10, help='Order of pickup within the route.')
    passenger_id = fields.Many2one(
        'res.partner',
        string='Passenger',
        required=True,
        domain=[('is_shuttle_passenger', '=', True)]
    )
    pickup_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Pickup Stop',
        domain=[('stop_type', 'in', ['pickup', 'both'])],
        ondelete='restrict'
    )
    dropoff_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Dropoff Stop',
        domain=[('stop_type', 'in', ['dropoff', 'both'])],
        ondelete='restrict'
    )
    seat_count = fields.Integer(
        string='Seats',
        default=1,
        help='Seats reserved for this passenger (for siblings, etc.).'
    )
    notes = fields.Char(string='Notes / Requirements', translate=True)
    company_id = fields.Many2one(
        'res.company',
        related='group_id.company_id',
        store=True,
        readonly=True
    )

    _sql_constraints = [
        ('unique_passenger_per_group',
         'unique(group_id, passenger_id)',
         'Passenger already exists in this group.'),
        ('positive_seat_requirement', 'CHECK(seat_count > 0)',
         'Seat count must be positive.'),
    ]

    def action_suggest_nearest_stop(self):
        """
        Suggest nearest stop for passenger based on GPS coordinates
        Returns dict with stop_id and distance
        """
        self.ensure_one()
        if not self.passenger_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('Please select a passenger first.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        passenger = self.passenger_id
        if not (passenger.shuttle_latitude and passenger.shuttle_longitude):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('Passenger does not have GPS coordinates. Please add coordinates first.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Get stop_type from context or default to pickup
        stop_type = self._context.get('stop_type', 'pickup')
        
        # Suggest stops via central service
        suggestions = self.env['shuttle.stop'].suggest_nearest(
            latitude=passenger.shuttle_latitude,
            longitude=passenger.shuttle_longitude,
            limit=1,
            stop_type=stop_type,
            company_id=self.company_id.id
        )

        if not suggestions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('No stops with GPS coordinates found.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        nearest = suggestions[0]
        nearest_stop = self.env['shuttle.stop'].browse(nearest['stop_id'])
        
        # Set the nearest stop
        if stop_type == 'pickup':
            self.pickup_stop_id = nearest_stop
        else:
            self.dropoff_stop_id = nearest_stop
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Nearest %s stop: %s (%.2f km away)') % (
                    stop_type, nearest_stop.name, nearest['distance_km']
                ),
                'type': 'success',
                'sticky': False,
            }
        }


# -*- coding: utf-8 -*-

import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShuttlePassengerGroup(models.Model):
    _name = 'shuttle.passenger.group'
    _description = 'Passenger Group / Route Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Group Name', required=True, tracking=True)
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
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    line_ids = fields.One2many(
        'shuttle.passenger.group.line',
        'group_id',
        string='Passengers'
    )
    member_count = fields.Integer(
        string='Passenger Count',
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
            group.member_count = len(group.line_ids)

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
        domain=[('stop_type', 'in', ['pickup', 'both'])]
    )
    dropoff_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Dropoff Stop',
        domain=[('stop_type', 'in', ['dropoff', 'both'])]
    )
    seat_count = fields.Integer(
        string='Seats',
        default=1,
        help='Seats reserved for this passenger (for siblings, etc.).'
    )
    notes = fields.Char(string='Notes / Requirements')
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

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate distance between two GPS coordinates using Haversine formula
        Returns distance in kilometers
        """
        if not all([lat1, lon1, lat2, lon2]):
            return None
        
        # Radius of Earth in kilometers
        R = 6371.0
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return distance

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
        
        # Get all stops of the requested type
        domain = [('stop_type', 'in', [stop_type, 'both']), ('active', '=', True)]
        stops = self.env['shuttle.stop'].search(domain)
        
        if not stops:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Warning'),
                    'message': _('No active stops found for %s.') % stop_type,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Calculate distances
        nearest_stop = None
        min_distance = float('inf')
        
        for stop in stops:
            if not (stop.latitude and stop.longitude):
                continue
            
            distance = self._calculate_distance(
                passenger.shuttle_latitude,
                passenger.shuttle_longitude,
                stop.latitude,
                stop.longitude
            )
            
            if distance is not None and distance < min_distance:
                min_distance = distance
                nearest_stop = stop
        
        if not nearest_stop:
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
                    stop_type, nearest_stop.name, min_distance
                ),
                'type': 'success',
                'sticky': False,
            }
        }


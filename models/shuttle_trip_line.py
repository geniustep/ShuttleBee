# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ShuttleTripLine(models.Model):
    _name = 'shuttle.trip.line'
    _description = 'Shuttle Trip Line (Passenger)'
    _order = 'sequence, id'

    # Relations
    trip_id = fields.Many2one(
        'shuttle.trip',
        string='Trip',
        required=True,
        ondelete='cascade',
        index=True
    )
    group_line_id = fields.Many2one(
        'shuttle.passenger.group.line',
        string='Group Line',
        help='Passenger group line this entry originated from'
    )
    passenger_id = fields.Many2one(
        'res.partner',
        string='Passenger',
        required=True,
        domain=[('is_shuttle_passenger', '=', True)],
        index=True
    )

    # Stops
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

    # GPS Coordinates (used when passenger has no assigned stop)
    pickup_latitude = fields.Float(
        string='Pickup Latitude',
        digits=(10, 7),
        help='GPS latitude for custom pickup location'
    )
    pickup_longitude = fields.Float(
        string='Pickup Longitude',
        digits=(10, 7),
        help='GPS longitude for custom pickup location'
    )
    dropoff_latitude = fields.Float(
        string='Dropoff Latitude',
        digits=(10, 7),
        help='GPS latitude for custom dropoff location'
    )
    dropoff_longitude = fields.Float(
        string='Dropoff Longitude',
        digits=(10, 7),
        help='GPS longitude for custom dropoff location'
    )

    # Capacity
    seat_count = fields.Integer(
        string='Seats Required',
        default=1,
        required=True
    )

    # Status
    status = fields.Selection([
        ('planned', 'Planned'),
        ('notified_approaching', 'Notified - Approaching'),
        ('notified_arrived', 'Notified - Arrived'),
        ('boarded', 'Boarded'),
        ('absent', 'Absent'),
        ('dropped', 'Dropped Off')
    ], string='Status', default='planned', required=True)

    # Sequence
    sequence = fields.Integer(
        string='Stop Sequence',
        default=10,
        help='Order of pickup/dropoff in the trip'
    )

    # Related Fields (for convenience)
    trip_date = fields.Date(
        related='trip_id.date',
        store=True,
        readonly=True
    )
    trip_type = fields.Selection(
        related='trip_id.trip_type',
        store=True,
        readonly=True
    )
    driver_id = fields.Many2one(
        related='trip_id.driver_id',
        store=True,
        readonly=True
    )

    # Notifications
    approaching_notified = fields.Boolean(
        string='Approaching Notified',
        default=False
    )
    arrived_notified = fields.Boolean(
        string='Arrived Notified',
        default=False
    )

    # Additional
    notes = fields.Text(string='Notes')
    color = fields.Integer(related='trip_id.color', store=False)
    company_id = fields.Many2one(
        related='trip_id.company_id',
        store=True,
        readonly=True
    )

    # Constraints
    _sql_constraints = [
        ('unique_passenger_trip', 'unique(trip_id, passenger_id)',
         'A passenger can only be added once per trip!'),
        ('positive_seats', 'CHECK(seat_count > 0)',
         'Seat count must be positive!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-set group_line_id if passenger is in the trip's group"""
        for vals in vals_list:
            if vals.get('trip_id') and vals.get('passenger_id') and not vals.get('group_line_id'):
                trip = self.env['shuttle.trip'].browse(vals['trip_id'])
                if trip.group_id:
                    group_line = trip.group_id.line_ids.filtered(
                        lambda l: l.passenger_id.id == vals['passenger_id']
                    )
                    if group_line:
                        vals['group_line_id'] = group_line[0].id
        return super().create(vals_list)
    
    def write(self, vals):
        """Auto-set group_line_id if passenger is in the trip's group"""
        if vals.get('passenger_id') or vals.get('trip_id'):
            for line in self:
                if line.trip_id and line.trip_id.group_id and not line.group_line_id:
                    if vals.get('passenger_id'):
                        passenger_id = vals['passenger_id']
                    elif line.passenger_id:
                        passenger_id = line.passenger_id.id
                    else:
                        continue
                    
                    group_line = line.trip_id.group_id.line_ids.filtered(
                        lambda l: l.passenger_id.id == passenger_id
                    )
                    if group_line:
                        vals['group_line_id'] = group_line[0].id
        return super().write(vals)
    
    @api.constrains('trip_id', 'group_line_id', 'passenger_id')
    def _check_group_line_required(self):
        """Ensure trip line comes from a passenger group or passenger is in the same group"""
        for line in self:
            if line.trip_id and line.trip_id.group_id and not line.group_line_id:
                # Check if passenger is in the same group
                group = line.trip_id.group_id
                passenger_in_group = group.line_ids.filtered(
                    lambda l: l.passenger_id.id == line.passenger_id.id
                )
                
                if not passenger_in_group:
                    raise ValidationError(_(
                        'Passenger %s is not in the Passenger Group "%s". '
                        'Please add the passenger to the group first, or reload passengers from the group.'
                    ) % (line.passenger_id.name, group.name))

    @api.constrains('pickup_stop_id', 'pickup_latitude', 'pickup_longitude',
                    'dropoff_stop_id', 'dropoff_latitude', 'dropoff_longitude', 'trip_type')
    def _check_stops(self):
        for line in self:
            # Pickup: must have either stop or coordinates
            if not line.pickup_stop_id and not (line.pickup_latitude and line.pickup_longitude):
                raise ValidationError(_('Pickup location must have either a Stop or GPS coordinates!'))
            
            # Dropoff: if stops are provided, they must be different
            if line.dropoff_stop_id and line.pickup_stop_id and line.pickup_stop_id == line.dropoff_stop_id:
                raise ValidationError(_('Pickup and dropoff stops must be different!'))
            
            # For dropoff trips: dropoff location must have either stop or coordinates
            if line.trip_type == 'dropoff':
                if not line.dropoff_stop_id and not (line.dropoff_latitude and line.dropoff_longitude):
                    raise ValidationError(_('Dropoff location must have either a Stop or GPS coordinates for dropoff trips!'))

    # Methods
    def action_mark_boarded(self):
        """Mark passenger as boarded"""
        self.write({'status': 'boarded'})
        for line in self:
            line.trip_id.message_post(
                body=_('Passenger %s has boarded.') % line.passenger_id.name
            )
        return True

    def action_mark_absent(self):
        """Mark passenger as absent"""
        self.write({'status': 'absent'})
        for line in self:
            line.trip_id.message_post(
                body=_('Passenger %s marked as absent.') % line.passenger_id.name
            )
        return True

    def action_mark_dropped(self):
        """Mark passenger as dropped off"""
        self.write({'status': 'dropped'})
        for line in self:
            line.trip_id.message_post(
                body=_('Passenger %s dropped off.') % line.passenger_id.name
            )
        return True

    def action_send_approaching_notification(self):
        """Send approaching notification"""
        for line in self:
            # Get template
            template = self.env.ref('shuttlebee.mail_template_approaching', raise_if_not_found=False)

            # Prepare message content
            pickup_location = line.pickup_stop_id.name if line.pickup_stop_id else _('your location')
            message_content = _(
                'Hello %s, Driver %s is approaching pickup point %s. ETA: 10 minutes.'
            ) % (
                line.passenger_id.name,
                line.driver_id.name,
                pickup_location
            )

            self.env['shuttle.notification'].create({
                'trip_id': line.trip_id.id,
                'trip_line_id': line.id,
                'passenger_id': line.passenger_id.id,
                'notification_type': 'approaching',
                'channel': 'sms',
                'message_content': message_content,
                'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
                'template_id': template.id if template else False,
            })._send_notification()

            line.write({
                'status': 'notified_approaching',
                'approaching_notified': True
            })
        return True

    def action_send_arrived_notification(self):
        """Send arrived notification"""
        for line in self:
            # Get template
            template = self.env.ref('shuttlebee.mail_template_arrived', raise_if_not_found=False)

            # Prepare message content
            pickup_location = line.pickup_stop_id.name if line.pickup_stop_id else _('your location')
            message_content = _(
                'Dear %s, Driver %s has arrived at %s. Please head to the shuttle immediately!'
            ) % (
                line.passenger_id.name,
                line.driver_id.name,
                pickup_location
            )

            self.env['shuttle.notification'].create({
                'trip_id': line.trip_id.id,
                'trip_line_id': line.id,
                'passenger_id': line.passenger_id.id,
                'notification_type': 'arrived',
                'channel': 'sms',
                'message_content': message_content,
                'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
                'template_id': template.id if template else False,
            })._send_notification()

            line.write({
                'status': 'notified_arrived',
                'arrived_notified': True
            })
        return True

    @api.onchange('passenger_id')
    def _onchange_passenger_id(self):
        """Auto-fill stops or coordinates from passenger defaults and set group_line_id"""
        if self.passenger_id and self.trip_id and self.trip_id.group_id:
            # Auto-set group_line_id if passenger is in the trip's group
            group = self.trip_id.group_id
            group_line = group.line_ids.filtered(
                lambda l: l.passenger_id.id == self.passenger_id.id
            )
            if group_line:
                self.group_line_id = group_line[0]
                # Use stops from group line if available
                if group_line[0].pickup_stop_id:
                    self.pickup_stop_id = group_line[0].pickup_stop_id
                if group_line[0].dropoff_stop_id:
                    self.dropoff_stop_id = group_line[0].dropoff_stop_id
                if group_line[0].seat_count:
                    self.seat_count = group_line[0].seat_count
            else:
                # If passenger not in group, use defaults from passenger
                self.pickup_stop_id = self.passenger_id.default_pickup_stop_id
                self.dropoff_stop_id = self.passenger_id.default_dropoff_stop_id
        elif self.passenger_id:
            # Set default stops from passenger
            self.pickup_stop_id = self.passenger_id.default_pickup_stop_id
            self.dropoff_stop_id = self.passenger_id.default_dropoff_stop_id
        
        if self.passenger_id:
            # If no pickup stop but passenger has coordinates, use them
            if not self.pickup_stop_id and self.passenger_id.shuttle_latitude and self.passenger_id.shuttle_longitude:
                self.pickup_latitude = self.passenger_id.shuttle_latitude
                self.pickup_longitude = self.passenger_id.shuttle_longitude
            
            # If no dropoff stop but passenger has coordinates, use them for dropoff too
            if not self.dropoff_stop_id and self.passenger_id.shuttle_latitude and self.passenger_id.shuttle_longitude:
                self.dropoff_latitude = self.passenger_id.shuttle_latitude
                self.dropoff_longitude = self.passenger_id.shuttle_longitude

    def name_get(self):
        """Custom name display"""
        result = []
        for line in self:
            if line.pickup_stop_id:
                location = line.pickup_stop_id.name
            elif line.pickup_latitude and line.pickup_longitude:
                location = f"GPS ({line.pickup_latitude:.4f}, {line.pickup_longitude:.4f})"
            else:
                location = _('No location')
            name = f"{line.passenger_id.name} - {location}"
            result.append((line.id, name))
        return result

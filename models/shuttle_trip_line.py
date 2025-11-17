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
        domain=[('stop_type', 'in', ['pickup', 'both'])],
        required=True
    )
    dropoff_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Dropoff Stop',
        domain=[('stop_type', 'in', ['dropoff', 'both'])]
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
    ], string='Status', default='planned', required=True, tracking=True)

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

    @api.constrains('pickup_stop_id', 'dropoff_stop_id')
    def _check_stops(self):
        for line in self:
            if line.dropoff_stop_id and line.pickup_stop_id == line.dropoff_stop_id:
                raise ValidationError(_('Pickup and dropoff stops must be different!'))

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
            message_content = _(
                'Hello %s, Driver %s is approaching pickup point %s. ETA: 10 minutes.'
            ) % (
                line.passenger_id.name,
                line.driver_id.name,
                line.pickup_stop_id.name
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
            message_content = _(
                'Dear %s, Driver %s has arrived at %s. Please head to the shuttle immediately!'
            ) % (
                line.passenger_id.name,
                line.driver_id.name,
                line.pickup_stop_id.name
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
        """Auto-fill stops from passenger defaults"""
        if self.passenger_id:
            self.pickup_stop_id = self.passenger_id.default_pickup_stop_id
            self.dropoff_stop_id = self.passenger_id.default_dropoff_stop_id

    def name_get(self):
        """Custom name display"""
        result = []
        for line in self:
            name = f"{line.passenger_id.name} - {line.pickup_stop_id.name}"
            result.append((line.id, name))
        return result

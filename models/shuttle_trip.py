# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ShuttleTrip(models.Model):
    _name = 'shuttle.trip'
    _description = 'Shuttle Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, planned_start_time desc'

    # Basic Information
    name = fields.Char(
        string='Trip Name',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        translate=True,
        tracking=True
    )
    reference = fields.Char(
        string='Reference',
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    trip_type = fields.Selection([
        ('pickup', 'Pickup (Morning)'),
        ('dropoff', 'Dropoff (Evening)')
    ], string='Trip Type', required=True, default='pickup', tracking=True)

    # Driver & Vehicle
    driver_id = fields.Many2one(
        'res.users',
        string='Driver',
        required=True,
        tracking=True,
        index=True
    )
    vehicle_id = fields.Many2one(
        'shuttle.vehicle',
        string='Vehicle',
        tracking=True,
        help='Vehicle used for this trip'
    )
    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Passenger Group',
        required=True,
        tracking=True,
        help='Group template used to generate this trip. Passengers will be loaded automatically from this group.'
    )

    # Date & Time
    date = fields.Date(
        string='Trip Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True
    )
    planned_start_time = fields.Datetime(
        string='Planned Start Time',
        required=True,
        tracking=True
    )
    planned_arrival_time = fields.Datetime(
        string='Planned Arrival Time',
        tracking=True
    )
    actual_start_time = fields.Datetime(
        string='Actual Start Time',
        readonly=True,
        tracking=True
    )
    actual_arrival_time = fields.Datetime(
        string='Actual Arrival Time',
        readonly=True,
        tracking=True
    )

    # Capacity
    total_seats = fields.Integer(
        string='Total Seats',
        required=True,
        default=15,
        tracking=True
    )

    # Relations
    line_ids = fields.One2many(
        'shuttle.trip.line',
        'trip_id',
        string='Passenger Lines'
    )
    stop_ids = fields.Many2many(
        'shuttle.stop',
        string='Stops',
        help='Pickup/Dropoff points for this trip'
    )

    # Computed Fields
    booked_seats = fields.Integer(
        string='Booked Seats',
        compute='_compute_seats',
        store=True
    )
    available_seats = fields.Integer(
        string='Available Seats',
        compute='_compute_seats',
        store=True
    )
    passenger_count = fields.Integer(
        string='Total Passengers',
        compute='_compute_passenger_stats',
        store=True
    )
    present_count = fields.Integer(
        string='Present',
        compute='_compute_passenger_stats',
        store=True
    )
    absent_count = fields.Integer(
        string='Absent',
        compute='_compute_passenger_stats',
        store=True
    )
    boarded_count = fields.Integer(
        string='Boarded',
        compute='_compute_passenger_stats',
        store=True
    )
    occupancy_rate = fields.Float(
        string='Occupancy Rate (%)',
        compute='_compute_occupancy_rate',
        store=True
    )

    # Duration
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    # Additional Info
    notes = fields.Text(string='Notes', translate=True)
    color = fields.Integer(string='Color Index', default=0)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    # Constraints
    @api.constrains('total_seats', 'booked_seats')
    def _check_seat_capacity(self):
        for trip in self:
            if trip.booked_seats > trip.total_seats:
                raise ValidationError(_('Booked seats cannot exceed total seats!'))
    
    @api.constrains('group_id', 'line_ids')
    def _check_group_required(self):
        """Ensure trip has a group and passengers come from group"""
        for trip in self:
            if not trip.group_id:
                raise ValidationError(_('Passenger Group is required for all trips!'))

    @api.constrains('planned_start_time', 'planned_arrival_time')
    def _check_times(self):
        for trip in self:
            if trip.planned_arrival_time and trip.planned_start_time:
                if trip.planned_arrival_time <= trip.planned_start_time:
                    raise ValidationError(_('Arrival time must be after start time!'))

    @api.constrains('actual_start_time', 'actual_arrival_time')
    def _check_actual_times(self):
        for trip in self:
            if trip.actual_arrival_time and trip.actual_start_time:
                if trip.actual_arrival_time <= trip.actual_start_time:
                    raise ValidationError(_('Actual arrival must be after actual start!'))

    # Computed Methods
    @api.depends('line_ids.seat_count')
    def _compute_seats(self):
        for trip in self:
            trip.booked_seats = sum(trip.line_ids.mapped('seat_count'))
            trip.available_seats = trip.total_seats - trip.booked_seats

    @api.depends('line_ids.status')
    def _compute_passenger_stats(self):
        for trip in self:
            trip.passenger_count = len(trip.line_ids)
            trip.present_count = len(trip.line_ids.filtered(
                lambda l: l.status in ['boarded', 'dropped']))
            trip.absent_count = len(trip.line_ids.filtered(
                lambda l: l.status == 'absent'))
            trip.boarded_count = len(trip.line_ids.filtered(
                lambda l: l.status == 'boarded'))

    @api.depends('booked_seats', 'total_seats')
    def _compute_occupancy_rate(self):
        for trip in self:
            if trip.total_seats > 0:
                trip.occupancy_rate = (trip.booked_seats / trip.total_seats) * 100
            else:
                trip.occupancy_rate = 0.0

    @api.depends('actual_start_time', 'actual_arrival_time')
    def _compute_duration(self):
        for trip in self:
            if trip.actual_start_time and trip.actual_arrival_time:
                delta = trip.actual_arrival_time - trip.actual_start_time
                trip.duration = delta.total_seconds() / 3600
            else:
                trip.duration = 0.0

    # Methods
    def action_confirm(self):
        """Confirm trip and change state to planned"""
        for trip in self:
            if not trip.line_ids:
                raise UserError(_('Cannot confirm trip without passengers!'))
            trip.write({'state': 'planned'})
            trip.message_post(body=_('Trip confirmed and ready to start.'))
        return True

    def action_start(self):
        """Start the trip"""
        for trip in self:
            trip.write({
                'state': 'ongoing',
                'actual_start_time': fields.Datetime.now()
            })
            trip.message_post(body=_('Trip started at %s') % trip.actual_start_time)
            # Send notifications to passengers
            trip._send_trip_started_notifications()
        return True

    def action_complete(self):
        """Complete the trip"""
        for trip in self:
            trip.write({
                'state': 'done',
                'actual_arrival_time': fields.Datetime.now()
            })
            trip.message_post(body=_('Trip completed at %s') % trip.actual_arrival_time)
        return True

    def action_cancel(self):
        """Cancel the trip"""
        for trip in self:
            trip.write({'state': 'cancelled'})
            trip.message_post(body=_('Trip cancelled.'))
            # Send cancellation notifications
            trip._send_cancellation_notifications()
        return True

    def action_reset_to_draft(self):
        """Reset to draft"""
        self.write({'state': 'draft'})
        return True

    def action_view_notifications(self):
        """View notifications for this trip"""
        self.ensure_one()
        return {
            'name': _('Notifications'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.notification',
            'view_mode': 'list,form',
            'domain': [('trip_id', '=', self.id)],
            'context': {'default_trip_id': self.id}
        }

    def _send_trip_started_notifications(self):
        """Send notifications when trip starts"""
        for trip in self:
            for line in trip.line_ids.filtered(lambda l: l.status == 'planned'):
                self.env['shuttle.notification'].create({
                    'trip_id': trip.id,
                    'trip_line_id': line.id,
                    'passenger_id': line.passenger_id.id,
                    'notification_type': 'trip_started',
                    'channel': 'sms',
                    'message_content': _('Trip %s has started. Driver: %s') % (
                        trip.name, trip.driver_id.name
                    ),
                    'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
                })._send_notification()

    def _send_cancellation_notifications(self):
        """Send cancellation notifications to all passengers"""
        for trip in self:
            for line in trip.line_ids:
                self.env['shuttle.notification'].create({
                    'trip_id': trip.id,
                    'trip_line_id': line.id,
                    'passenger_id': line.passenger_id.id,
                    'notification_type': 'cancelled',
                    'channel': 'sms',
                    'message_content': _('Trip %s has been cancelled.') % trip.name,
                    'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
                })._send_notification()

    @api.model
    def create(self, vals):
        """Override create to generate sequence"""
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].next_by_code(
                'shuttle.trip') or _('New')
        return super().create(vals)

    def name_get(self):
        """Custom name display"""
        result = []
        for trip in self:
            name = f"[{trip.reference}] {trip.name} - {trip.date}"
            result.append((trip.id, name))
        return result

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        for trip in self:
            if trip.vehicle_id:
                trip.total_seats = trip.vehicle_id.seat_capacity
                if trip.vehicle_id.driver_id:
                    trip.driver_id = trip.vehicle_id.driver_id

    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Load passengers from selected group"""
        for trip in self:
            if trip.group_id:
                # Set default values from group
                if not trip.driver_id and trip.group_id.driver_id:
                    trip.driver_id = trip.group_id.driver_id
                if not trip.vehicle_id and trip.group_id.vehicle_id:
                    trip.vehicle_id = trip.group_id.vehicle_id
                if not trip.total_seats and trip.group_id.total_seats:
                    trip.total_seats = trip.group_id.total_seats
                
                # Load passengers from group (only if trip is new or has no lines)
                if not trip.line_ids:
                    line_vals = trip.group_id._prepare_trip_line_values(trip_type=trip.trip_type)
                    # We'll create lines after save, but show them in UI
                    trip.line_ids = [(0, 0, vals) for vals in line_vals]

    # Cron Methods
    @api.model
    def _cron_send_approaching_notifications(self):
        """Send approaching notifications for upcoming trips"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        approaching_minutes = int(IrConfigParam.get_param(
            'shuttlebee.approaching_minutes', 10))

        now = fields.Datetime.now()
        target_time = now + timedelta(minutes=approaching_minutes)

        # Find trips that should send notifications
        trips = self.search([
            ('state', '=', 'planned'),
            ('planned_start_time', '<=', target_time),
            ('planned_start_time', '>', now),
        ])

        for trip in trips:
            for line in trip.line_ids.filtered(
                lambda l: l.status == 'planned' and not l.approaching_notified
            ):
                line.action_send_approaching_notification()

        return True

    @api.model
    def _cron_mark_absent_passengers(self):
        """Auto-mark passengers as absent if they haven't boarded"""
        IrConfigParam = self.env['ir.config_parameter'].sudo()
        absent_timeout = int(IrConfigParam.get_param(
            'shuttlebee.absent_timeout', 5))

        now = fields.Datetime.now()
        timeout_time = now - timedelta(minutes=absent_timeout)

        # Find ongoing trips
        trips = self.search([
            ('state', '=', 'ongoing'),
            ('actual_start_time', '<=', timeout_time),
        ])

        for trip in trips:
            for line in trip.line_ids.filtered(
                lambda l: l.status not in ['boarded', 'absent', 'dropped']
            ):
                line.action_mark_absent()

        return True

    @api.model
    def _cron_send_daily_summary(self):
        """Send daily trip summary to managers"""
        today = fields.Date.today()
        trips = self.search([('date', '=', today)])

        if not trips:
            return True

        # Prepare summary
        total_trips = len(trips)
        total_passengers = sum(trips.mapped('passenger_count'))
        total_present = sum(trips.mapped('present_count'))
        total_absent = sum(trips.mapped('absent_count'))

        # Get manager group
        try:
            manager_group = self.env.ref('shuttlebee.group_shuttle_manager')
            manager_users = manager_group.users

            # Send email to each manager
            template = self.env.ref('shuttlebee.email_template_daily_summary')
            for user in manager_users:
                template.with_context(
                    user=user,
                    total_trips=total_trips,
                    total_passengers=total_passengers,
                    total_present=total_present,
                    total_absent=total_absent,
                    attendance_rate=(total_present/total_passengers*100 if total_passengers else 0),
                    today=today
                ).send_mail(user.id, force_send=True)
        except Exception as e:
            _logger.warning(f"Could not send daily summary: {str(e)}")

        return True

    @api.model
    def _expand_states(self, states, domain, order):
        """Expand states for kanban group_by"""
        return [key for key, val in type(self).state.selection]

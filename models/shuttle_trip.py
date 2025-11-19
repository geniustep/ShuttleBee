# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger('shuttlebee.trip')


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
        index=True,
        help='Vehicle used for this trip'
    )
    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Passenger Group',
        required=True,
        tracking=True,
        ondelete='restrict',
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
    total_passengers = fields.Integer(
        string='Total Passengers (Legacy)',
        compute='_compute_passenger_stats',
        store=True,
        help='Alias for passenger_count to support external clients.'
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
    planned_duration = fields.Float(
        string='Planned Duration (Hours)',
        compute='_compute_time_metrics',
        store=True,
        help='Duration between planned start and arrival times.'
    )
    actual_duration = fields.Float(
        string='Actual Duration (Hours)',
        compute='_compute_time_metrics',
        store=True,
        help='Duration between actual start and arrival times.'
    )
    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_time_metrics',
        store=True,
        help='Backwards-compatible alias of actual_duration.'
    )
    delay_minutes = fields.Float(
        string='Delay (Minutes)',
        compute='_compute_time_metrics',
        store=True,
        help='Positive means late arrival, negative means early.'
    )
    current_latitude = fields.Float(
        string='Current Latitude',
        digits=(10, 7),
        help='Latest reported latitude for this trip.',
        tracking=True
    )
    current_longitude = fields.Float(
        string='Current Longitude',
        digits=(10, 7),
        help='Latest reported longitude for this trip.',
        tracking=True
    )
    last_gps_update = fields.Datetime(
        string='Last GPS Update',
        tracking=True,
        help='Timestamp of the last GPS coordinate received.'
    )
    weather_status = fields.Selection([
        ('clear', 'Clear'),
        ('rain', 'Rain'),
        ('storm', 'Storm'),
        ('fog', 'Fog'),
        ('snow', 'Snow'),
        ('unknown', 'Unknown'),
    ], string='Weather Status', default='unknown', tracking=True)
    traffic_status = fields.Selection([
        ('normal', 'Normal'),
        ('heavy', 'Heavy'),
        ('jam', 'Traffic Jam'),
        ('accident', 'Accident'),
        ('unknown', 'Unknown'),
    ], string='Traffic Status', default='unknown', tracking=True)
    external_risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Risk Level', default='low', tracking=True)

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('planned', 'Planned'),
        ('ongoing', 'Ongoing'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True, index=True)

    # Additional Info
    notes = fields.Text(string='Notes', translate=True)
    color = fields.Integer(string='Color Index', default=0)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True
    )
    active = fields.Boolean(default=True)

    # Constraints
    @api.constrains('total_seats', 'booked_seats')
    def _check_seat_capacity(self):
        for trip in self:
            if trip.booked_seats > trip.total_seats:
                raise ValidationError(_('Booked seats cannot exceed total seats!'))
            vehicle = trip.vehicle_id
            if vehicle and trip.total_seats > vehicle.seat_capacity:
                raise ValidationError(_('Trip seats (%s) cannot exceed vehicle capacity (%s).') % (
                    trip.total_seats, vehicle.seat_capacity))
    
    @api.constrains('group_id', 'line_ids')
    def _check_group_required(self):
        """Ensure trip has a group and passengers come from group"""
        for trip in self:
            if not trip.group_id:
                raise ValidationError(_('Passenger Group is required for all trips!'))
            if trip.state != 'draft' and not trip.line_ids:
                raise ValidationError(_('Trip must have at least one passenger before confirmation!'))

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
        """Compute passenger statistics efficiently"""
        for trip in self:
            lines = trip.line_ids
            total = len(lines)
            trip.passenger_count = total
            trip.total_passengers = total
            
            # Use single pass through lines for better performance
            present_count = 0
            absent_count = 0
            boarded_count = 0
            
            for line in lines:
                status = line.status
                if status in ['boarded', 'dropped']:
                    present_count += 1
                if status == 'absent':
                    absent_count += 1
                if status == 'boarded':
                    boarded_count += 1
            
            trip.present_count = present_count
            trip.absent_count = absent_count
            trip.boarded_count = boarded_count

    @api.depends('booked_seats', 'total_seats')
    def _compute_occupancy_rate(self):
        for trip in self:
            if trip.total_seats > 0:
                trip.occupancy_rate = (trip.booked_seats / trip.total_seats) * 100
            else:
                trip.occupancy_rate = 0.0

    @api.depends('planned_start_time', 'planned_arrival_time', 'actual_start_time', 'actual_arrival_time')
    def _compute_time_metrics(self):
        for trip in self:
            # Planned duration
            if trip.planned_start_time and trip.planned_arrival_time:
                planned_seconds = (trip.planned_arrival_time - trip.planned_start_time).total_seconds()
                trip.planned_duration = max(planned_seconds / 3600, 0)
            else:
                trip.planned_duration = 0.0

            # Actual duration
            if trip.actual_start_time and trip.actual_arrival_time:
                actual_seconds = (trip.actual_arrival_time - trip.actual_start_time).total_seconds()
                actual_hours = max(actual_seconds / 3600, 0)
                trip.actual_duration = actual_hours
                trip.duration = actual_hours
            else:
                trip.actual_duration = 0.0
                trip.duration = 0.0

            # Delay (minutes)
            if trip.actual_arrival_time and trip.planned_arrival_time:
                trip.delay_minutes = (trip.actual_arrival_time - trip.planned_arrival_time).total_seconds() / 60
            else:
                trip.delay_minutes = 0.0

    # Methods
    def action_confirm(self):
        """Confirm trip and change state to planned"""
        for trip in self:
            if not trip.group_id:
                raise UserError(_('Please select a passenger group before confirming the trip.'))
            if not trip.line_ids:
                raise UserError(_('You need at least one passenger before confirming the trip.'))
            if not trip.driver_id:
                raise UserError(_('Please assign a driver before confirming the trip.'))
            if not trip.planned_start_time:
                raise UserError(_('Please set a planned start time before confirming the trip.'))
            if trip.total_seats <= 0:
                raise UserError(_('Trip must have a positive number of seats.'))
            
            trip.write({'state': 'planned'})
            trip._log_event(_('Trip confirmed and ready to start.'))
        return True

    def action_start_trip(self):
        """API-friendly start action with summary response"""
        results = []
        total_sent = 0
        total_failed = 0
        for trip in self:
            if trip.state != 'planned':
                raise UserError(_('You can only start trips that are in the Planned state.'))
            if not trip.driver_id:
                raise UserError(_('Please assign a driver before starting the trip.'))
            if not trip.line_ids:
                raise UserError(_('You cannot start a trip without any passengers.'))

            trip.write({
                'state': 'ongoing',
                'actual_start_time': fields.Datetime.now()
            })
            trip._log_event(_('Trip started at %s') % trip.actual_start_time)

            notification_summary = trip._send_trip_started_notifications().get(trip.id, {
                'sent': 0,
                'failed': 0,
                'errors': [],
                'lines_processed': 0,
            })
            total_sent += notification_summary.get('sent', 0)
            total_failed += notification_summary.get('failed', 0)

            results.append({
                'trip_id': trip.id,
                'name': trip.name,
                'new_state': trip.state,
                'actual_start_time': trip.actual_start_time,
                'notifications_sent': notification_summary.get('sent', 0),
                'notification_failures': notification_summary.get('failed', 0),
                'notification_errors': notification_summary.get('errors', []),
            })

        return {
            'trip_ids': self.ids,
            'trips_processed': len(self),
            'notifications_sent': total_sent,
            'notification_failures': total_failed,
            'results': results,
        }

    def action_start(self):
        """Start the trip"""
        self.action_start_trip()
        return True

    def action_complete_trip(self):
        """API-friendly complete action"""
        results = []
        for trip in self:
            if trip.state != 'ongoing':
                raise UserError(_('Only trips that are in progress can be marked as done.'))
            if not trip.actual_start_time:
                raise UserError(_('Trip must have an actual start time before you can complete it.'))

            # Mark all passengers who are not absent as present
            # For pickup trips: mark as 'boarded' if not already 'boarded' or 'dropped'
            # For dropoff trips: mark as 'dropped' if not already 'dropped'
            for line in trip.line_ids:
                if line.status != 'absent':
                    if trip.trip_type == 'pickup':
                        # For pickup trips, mark as 'boarded' if not already 'boarded' or 'dropped'
                        if line.status not in ['boarded', 'dropped']:
                            line.write({
                                'status': 'boarded',
                                'boarding_time': fields.Datetime.now() if not line.boarding_time else line.boarding_time,
                            })
                    elif trip.trip_type == 'dropoff':
                        # For dropoff trips, mark as 'dropped' if not already 'dropped'
                        if line.status != 'dropped':
                            line.write({
                                'status': 'dropped',
                            })

            trip.write({
                'state': 'done',
                'actual_arrival_time': fields.Datetime.now()
            })
            trip._log_event(_('Trip completed at %s') % trip.actual_arrival_time)

            results.append({
                'trip_id': trip.id,
                'name': trip.name,
                'new_state': trip.state,
                'actual_arrival_time': trip.actual_arrival_time,
            })

        return {
            'trip_ids': self.ids,
            'trips_completed': len(results),
            'results': results,
        }

    def action_complete(self):
        """Complete the trip"""
        self.action_complete_trip()

    def action_mark_all_boarded(self):
        """Mark all passengers who are not absent as boarded"""
        self.ensure_one()
        if self.state != 'ongoing':
            raise UserError(_('Only trips that are in progress can mark passengers as boarded.'))
        
        # Mark all passengers who are not absent as boarded
        marked_count = 0
        for line in self.line_ids:
            if line.status != 'absent' and line.status != 'boarded':
                line.write({
                    'status': 'boarded',
                    'boarding_time': fields.Datetime.now() if not line.boarding_time else line.boarding_time,
                })
                marked_count += 1
        
        if marked_count > 0:
            self.message_post(
                body=_('Marked %s passenger(s) as boarded.') % marked_count
            )
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Marked %s passenger(s) as boarded.') % marked_count,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Info'),
                    'message': _('All passengers are already boarded or absent.'),
                    'type': 'info',
                }
            }
        return True

    def action_cancel_trip(self):
        """API-friendly cancel action"""
        results = []
        total_sent = 0
        total_failed = 0
        for trip in self:
            if trip.state in ['done', 'cancelled']:
                raise UserError(_('You cannot cancel a trip that is already %s.') % dict(self._fields['state'].selection).get(trip.state))

            trip.write({'state': 'cancelled'})
            trip._log_event(_('Trip cancelled.'))

            notification_summary = trip._send_cancellation_notifications().get(trip.id, {
                'sent': 0,
                'failed': 0,
                'errors': [],
                'lines_processed': 0,
            })
            total_sent += notification_summary.get('sent', 0)
            total_failed += notification_summary.get('failed', 0)

            results.append({
                'trip_id': trip.id,
                'name': trip.name,
                'new_state': trip.state,
                'notifications_sent': notification_summary.get('sent', 0),
                'notification_failures': notification_summary.get('failed', 0),
                'notification_errors': notification_summary.get('errors', []),
            })

        return {
            'trip_ids': self.ids,
            'trips_cancelled': len(results),
            'notifications_sent': total_sent,
            'notification_failures': total_failed,
            'results': results,
        }

    def action_cancel(self):
        """Cancel the trip"""
        self.action_cancel_trip()
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
        """Send notifications when trip starts and return summary"""
        Notification = self.env['shuttle.notification']
        summaries = {}
        for trip in self:
            data = {
                'trip_id': trip.id,
                'sent': 0,
                'failed': 0,
                'errors': [],
                'lines_processed': 0,
            }
            planned_lines = trip.line_ids.filtered(lambda l: l.status == 'planned')
            data['lines_processed'] = len(planned_lines)
            for line in planned_lines:
                try:
                    Notification.create({
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
                    data['sent'] += 1
                except Exception as error:
                    data['failed'] += 1
                    error_msg = str(error)
                    data['errors'].append({
                        'trip_line_id': line.id,
                        'message': error_msg,
                    })
                    _logger.error(
                        'Failed to send start notification for trip %s line %s: %s',
                        trip.id, line.id, error_msg, exc_info=True
                    )
            summaries[trip.id] = data
            trip._log_event(_('Sent %(sent)s start notifications (%(failed)s failed).', sent=data['sent'], failed=data['failed']))
        return summaries

    def _send_cancellation_notifications(self):
        """Send cancellation notifications to all passengers and return summary"""
        Notification = self.env['shuttle.notification']
        summaries = {}
        for trip in self:
            data = {
                'trip_id': trip.id,
                'sent': 0,
                'failed': 0,
                'errors': [],
                'lines_processed': len(trip.line_ids),
            }
            for line in trip.line_ids:
                try:
                    Notification.create({
                    'trip_id': trip.id,
                    'trip_line_id': line.id,
                    'passenger_id': line.passenger_id.id,
                    'notification_type': 'cancelled',
                    'channel': 'sms',
                    'message_content': _('Trip %s has been cancelled.') % trip.name,
                    'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
                })._send_notification()
                    data['sent'] += 1
                except Exception as error:
                    data['failed'] += 1
                    error_msg = str(error)
                    data['errors'].append({
                        'trip_line_id': line.id,
                        'message': error_msg,
                    })
                    _logger.error(
                        'Failed to send cancellation notification for trip %s line %s: %s',
                        trip.id, line.id, error_msg, exc_info=True
                    )
            summaries[trip.id] = data
            trip._log_event(_('Sent %(sent)s cancellation notifications (%(failed)s failed).', sent=data['sent'], failed=data['failed']))
        return summaries

    def action_send_approaching_notifications(self):
        """Send approaching notifications for all eligible passengers in the trips"""
        trip_results = []
        total_sent = 0
        total_failed = 0
        total_lines = 0

        for trip in self:
            lines = trip.line_ids.filtered(
                lambda l: l.status == 'planned' and not l.approaching_notified
            )
            trip_summary = {
                'trip_id': trip.id,
                'lines_processed': len(lines),
                'notifications_sent': 0,
                'notification_failures': 0,
                'errors': [],
            }
            total_lines += len(lines)

            for line in lines:
                try:
                    line.action_send_approaching_notification()
                    trip_summary['notifications_sent'] += 1
                except Exception as error:
                    trip_summary['notification_failures'] += 1
                    error_msg = str(error)
                    trip_summary['errors'].append({
                        'trip_line_id': line.id,
                        'message': error_msg,
                    })
                    _logger.error(
                        'Failed to send approaching notification for trip %s line %s: %s',
                        trip.id, line.id, error_msg, exc_info=True
                    )

            total_sent += trip_summary['notifications_sent']
            total_failed += trip_summary['notification_failures']
            trip_results.append(trip_summary)
            if trip_summary['lines_processed']:
                trip._log_event(_('Sent %(sent)s approaching notifications (%(failed)s failed).', sent=trip_summary['notifications_sent'], failed=trip_summary['notification_failures']))

        return {
            'trip_ids': self.ids,
            'trip_count': len(self),
            'total_lines_processed': total_lines,
            'total_sent': total_sent,
            'total_failed': total_failed,
            'trip_results': trip_results,
        }

    def action_send_arrived_notifications(self):
        """Send arrived notifications for eligible passengers"""
        trip_results = []
        total_sent = 0
        total_failed = 0
        total_lines = 0

        for trip in self:
            lines = trip.line_ids.filtered(
                lambda l: l.status in ['planned', 'notified_approaching'] and not l.arrived_notified
            )
            trip_summary = {
                'trip_id': trip.id,
                'lines_processed': len(lines),
                'notifications_sent': 0,
                'notification_failures': 0,
                'errors': [],
            }
            total_lines += len(lines)

            for line in lines:
                try:
                    line.action_send_arrived_notification()
                    trip_summary['notifications_sent'] += 1
                except Exception as error:
                    trip_summary['notification_failures'] += 1
                    error_msg = str(error)
                    trip_summary['errors'].append({
                        'trip_line_id': line.id,
                        'message': error_msg,
                    })
                    _logger.error(
                        'Failed to send arrived notification for trip %s line %s: %s',
                        trip.id, line.id, error_msg, exc_info=True
                    )

            total_sent += trip_summary['notifications_sent']
            total_failed += trip_summary['notification_failures']
            trip_results.append(trip_summary)
            if trip_summary['lines_processed']:
                trip._log_event(_('Sent %(sent)s arrival notifications (%(failed)s failed).', sent=trip_summary['notifications_sent'], failed=trip_summary['notification_failures']))

        return {
            'trip_ids': self.ids,
            'trip_count': len(self),
            'total_lines_processed': total_lines,
            'total_sent': total_sent,
            'total_failed': total_failed,
            'trip_results': trip_results,
        }

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

    # Service Helpers
    def _prepare_trip_datetime(self, value, field_name):
        """Ensure incoming date/datetime values are converted properly"""
        if not value:
            return False
        try:
            if isinstance(value, str):
                return fields.Datetime.to_datetime(value)
            return fields.Datetime.to_datetime(value)
        except Exception:
            raise ValidationError(_('Invalid %s value: %s') % (field_name, value))

    def _prepare_trip_date(self, value, field_name):
        if not value:
            raise ValidationError(_('Field %s is required.') % field_name)
        try:
            if isinstance(value, str):
                return fields.Date.to_date(value)
            return fields.Date.to_date(value)
        except Exception:
            raise ValidationError(_('Invalid %s value: %s') % (field_name, value))

    def _create_trip_from_group(self, group, trip_type, trip_date, start_time, arrival_time=False,
                                driver=False, vehicle=False, total_seats=False, notes=False):
        """Internal helper used by service and wizard to generate trips"""
        if not group:
            raise UserError(_('Passenger group is required to create trips.'))
        if not start_time:
            raise UserError(_('Start time is required to create %s trip.') % trip_type)

        vehicle = vehicle or group.vehicle_id
        driver = driver or group.driver_id or (vehicle.driver_id if vehicle and vehicle.driver_id else False)
        seats = total_seats or group.total_seats or (vehicle.seat_capacity if vehicle else 0)
        seat_required = sum(group.line_ids.mapped('seat_count'))
        if seats and seat_required > seats:
            raise UserError(_(
                'Passenger seats (%s) exceed selected capacity (%s).'
            ) % (seat_required, seats))

        vals = {
            'name': '%s - %s' % (group.name, trip_type.title()),
            'trip_type': trip_type,
            'date': trip_date,
            'planned_start_time': start_time,
            'planned_arrival_time': arrival_time,
            'driver_id': driver.id if driver else False,
            'vehicle_id': vehicle.id if vehicle else False,
            'total_seats': seats,
            'notes': notes or group.notes,
            'group_id': group.id,
        }

        trip = self.create(vals)

        line_vals = group._prepare_trip_line_values(trip.id, trip_type)
        self.env['shuttle.trip.line'].create(line_vals)

        stop_ids = set()
        for line in group.line_ids:
            if trip_type == 'pickup' and line.pickup_stop_id:
                stop_ids.add(line.pickup_stop_id.id)
            if trip_type == 'dropoff' and line.dropoff_stop_id:
                stop_ids.add(line.dropoff_stop_id.id)
        if stop_ids:
            trip.stop_ids = [(6, 0, list(stop_ids))]

        return trip

    # Service Methods (API-friendly)
    @api.model
    def action_generate_from_group(
        self, group_id, trip_date, pickup_time=False, dropoff_time=False,
        create_pickup=True, create_dropoff=False,
        pickup_arrival_time=False, dropoff_arrival_time=False,
        driver_id=False, vehicle_id=False, total_seats=False, notes=False
    ):
        """Public service to generate trips from groups without using the wizard"""
        if not group_id:
            raise UserError(_('Passenger group is required.'))

        group = self.env['shuttle.passenger.group'].browse(group_id)
        if not group.exists():
            raise UserError(_('Passenger group not found.'))

        if not create_pickup and not create_dropoff:
            raise UserError(_('Please enable at least one trip type (pickup/dropoff).'))

        trip_date = self._prepare_trip_date(trip_date, 'trip_date')
        driver = self.env['res.users'].browse(driver_id) if driver_id else False
        vehicle = self.env['shuttle.vehicle'].browse(vehicle_id) if vehicle_id else False

        created_trips = self.browse()
        pickup_trips = self.browse()
        dropoff_trips = self.browse()

        if create_pickup:
            if not pickup_time:
                raise UserError(_('Pickup start time is required to create pickup trip.'))
            pickup_start = self._prepare_trip_datetime(pickup_time, 'pickup_time')
            pickup_arrival = self._prepare_trip_datetime(pickup_arrival_time, 'pickup_arrival_time') if pickup_arrival_time else False
            pickup_trip = self._create_trip_from_group(
                group=group,
                trip_type='pickup',
                trip_date=trip_date,
                start_time=pickup_start,
                arrival_time=pickup_arrival,
                driver=driver,
                vehicle=vehicle,
                total_seats=total_seats,
                notes=notes
            )
            pickup_trips |= pickup_trip
            created_trips |= pickup_trip

        if create_dropoff:
            if not dropoff_time:
                raise UserError(_('Dropoff start time is required to create dropoff trip.'))
            dropoff_start = self._prepare_trip_datetime(dropoff_time, 'dropoff_time')
            dropoff_arrival = self._prepare_trip_datetime(dropoff_arrival_time, 'dropoff_arrival_time') if dropoff_arrival_time else False
            dropoff_trip = self._create_trip_from_group(
                group=group,
                trip_type='dropoff',
                trip_date=trip_date,
                start_time=dropoff_start,
                arrival_time=dropoff_arrival,
                driver=driver,
                vehicle=vehicle,
                total_seats=total_seats,
                notes=notes
            )
            dropoff_trips |= dropoff_trip
            created_trips |= dropoff_trip

        result = {
            'trip_ids': created_trips.ids,
            'created_count': len(created_trips),
            'pickup_trip_ids': pickup_trips.ids,
            'dropoff_trip_ids': dropoff_trips.ids,
        }
        return result

    @api.model
    def register_gps_position(self, trip_id, latitude, longitude, speed=None, heading=None, timestamp=None):
        """Register a real-time GPS point for a trip (called by driver app/device)."""
        if not trip_id:
            raise ValidationError(_('Trip ID is required to register GPS data.'))

        trip = self.browse(trip_id)
        if not trip.exists():
            raise ValidationError(_('Trip not found.'))
        if trip.state != 'ongoing':
            raise UserError(_('You can only send GPS positions for trips that are in progress.'))

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            raise ValidationError(_('Latitude and longitude must be numeric values.'))

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValidationError(_('Latitude must be between -90 and 90, and longitude between -180 and 180.'))

        vals = {
            'trip_id': trip.id,
            'vehicle_id': trip.vehicle_id.id,
            'driver_id': trip.driver_id.id,
            'latitude': latitude,
            'longitude': longitude,
            'speed': speed,
            'heading': heading,
            'timestamp': timestamp or fields.Datetime.now(),
        }
        gps_point = self.env['shuttle.gps.position'].create(vals)

        trip.write({
            'current_latitude': latitude,
            'current_longitude': longitude,
            'last_gps_update': gps_point.timestamp,
        })

        return {
            'status': 'ok',
            'trip_id': trip.id,
            'timestamp': gps_point.timestamp,
        }

    @api.model
    def update_trip_conditions(self, trip_id, weather_status=None, traffic_status=None, risk_level=None):
        """Update weather/traffic/risk indicators for a trip."""
        trip = self.browse(trip_id)
        if not trip.exists():
            raise ValidationError(_('Trip not found.'))

        vals = {}
        selection_fields = {
            'weather_status': weather_status,
            'traffic_status': traffic_status,
            'external_risk_level': risk_level,
        }
        for field_name, value in selection_fields.items():
            if value is None:
                continue
            field = self._fields[field_name]
            allowed = dict(field.selection).keys()
            if value not in allowed:
                raise ValidationError(_('Invalid value "%(value)s" for %(field)s.') % {
                    'value': value,
                    'field': field.string,
                })
            vals[field_name] = value

        if vals:
            trip.write(vals)
            trip._log_event(_('Trip conditions updated: %(vals)s', vals=vals))

        return {'status': 'ok', 'updated_fields': list(vals.keys())}

    # Logging helpers
    def _log_event(self, message):
        """Post a message on the trip chatter for timeline tracking"""
        for trip in self:
            trip.message_post(body=message)

    @api.model
    def get_dashboard_stats(self, date_from, date_to, company_id=None):
        """Return aggregated trip statistics for dashboards or reports"""
        date_start = self._prepare_trip_date(date_from, 'date_from')
        date_end = self._prepare_trip_date(date_to, 'date_to')
        if date_end < date_start:
            raise ValidationError(_('date_to must be greater than or equal to date_from'))

        domain = [
            ('date', '>=', date_start),
            ('date', '<=', date_end),
        ]

        company = False
        if company_id:
            company = self.env['res.company'].browse(company_id)
            if not company.exists():
                raise UserError(_('Company not found.'))
            domain.append(('company_id', '=', company.id))

        trips = self.search(domain)
        if not trips:
            return {
                'date_from': date_start,
                'date_to': date_end,
                'company_id': company.id if company else False,
                'total_trips': 0,
                'total_passengers': 0,
                'present_count': 0,
                'absent_count': 0,
                'avg_occupancy_rate': 0.0,
            }

        total_trips = len(trips)
        total_passengers = sum(trips.mapped('passenger_count'))
        present_count = sum(trips.mapped('present_count'))
        absent_count = sum(trips.mapped('absent_count'))
        occupancy_sum = sum(trips.mapped('occupancy_rate'))
        avg_occupancy_rate = occupancy_sum / total_trips if total_trips else 0.0

        return {
            'date_from': date_start,
            'date_to': date_end,
            'company_id': company.id if company else False,
            'total_trips': total_trips,
            'total_passengers': total_passengers,
            'present_count': present_count,
            'absent_count': absent_count,
            'avg_occupancy_rate': avg_occupancy_rate,
        }

    # Cron Methods
    @api.model
    def _cron_send_approaching_notifications(self):
        """Send approaching notifications for upcoming trips"""
        try:
            IrConfigParam = self.env['ir.config_parameter'].sudo()
            approaching_minutes = int(IrConfigParam.get_param(
                'shuttlebee.approaching_minutes', 10))

            if approaching_minutes <= 0:
                _logger.warning('Approaching minutes is set to invalid value: %s. Using default 10.', approaching_minutes)
                approaching_minutes = 10

            now = fields.Datetime.now()
            target_time = now + timedelta(minutes=approaching_minutes)

            # Find trips that should send notifications
            trips = self.search([
                ('state', '=', 'planned'),
                ('planned_start_time', '<=', target_time),
                ('planned_start_time', '>', now),
            ])

            if not trips:
                _logger.debug('No trips found for approaching notifications')
                return True

            summary = trips.action_send_approaching_notifications()
            _logger.info(
                "Approaching notifications cron completed: %s sent, %s failed across %s trips",
                summary.get('total_sent', 0),
                summary.get('total_failed', 0),
                summary.get('trip_count', len(trips))
            )

        except Exception as e:
            _logger.error(
                f"Critical error in _cron_send_approaching_notifications: {str(e)}",
                exc_info=True
            )
            # Don't raise - allow cron to continue

        return True

    @api.model
    def _cron_mark_absent_passengers(self):
        """Auto-mark passengers as absent if they haven't boarded"""
        try:
            IrConfigParam = self.env['ir.config_parameter'].sudo()
            absent_timeout = int(IrConfigParam.get_param(
                'shuttlebee.absent_timeout', 5))

            if absent_timeout <= 0:
                _logger.warning('Absent timeout is set to invalid value: %s. Using default 5.', absent_timeout)
                absent_timeout = 5

            now = fields.Datetime.now()
            timeout_time = now - timedelta(minutes=absent_timeout)

            # Find ongoing trips
            trips = self.search([
                ('state', '=', 'ongoing'),
                ('actual_start_time', '<=', timeout_time),
            ])

            if not trips:
                _logger.debug('No ongoing trips found for marking absent passengers')
                return True

            marked_count = 0
            error_count = 0

            for trip in trips:
                try:
                    for line in trip.line_ids.filtered(
                        lambda l: l.status not in ['boarded', 'absent', 'dropped']
                    ):
                        try:
                            line.action_mark_absent()
                            marked_count += 1
                        except Exception as e:
                            error_count += 1
                            _logger.error(
                                f"Failed to mark absent for trip line {line.id} "
                                f"in trip {trip.id}: {str(e)}",
                                exc_info=True
                            )
                except Exception as e:
                    error_count += 1
                    _logger.error(
                        f"Error processing trip {trip.id} for marking absent: {str(e)}",
                        exc_info=True
                    )

            _logger.info(
                f"Mark absent passengers cron completed: {marked_count} marked, "
                f"{error_count} errors out of {len(trips)} trips"
            )

        except Exception as e:
            _logger.error(
                f"Critical error in _cron_mark_absent_passengers: {str(e)}",
                exc_info=True
            )
            # Don't raise - allow cron to continue

        return True

    @api.model
    def _cron_send_daily_summary(self):
        """Send daily trip summary to managers"""
        try:
            today = fields.Date.today()
            trips = self.search([('date', '=', today)])

            if not trips:
                _logger.debug(f'No trips found for date {today} - skipping daily summary')
                return True

            # Prepare summary
            total_trips = len(trips)
            total_passengers = sum(trips.mapped('passenger_count')) or 0
            total_present = sum(trips.mapped('present_count')) or 0
            total_absent = sum(trips.mapped('absent_count')) or 0
            attendance_rate = (total_present / total_passengers * 100) if total_passengers > 0 else 0

            # Get manager group
            try:
                manager_group = self.env.ref('shuttlebee.group_shuttle_manager')
                manager_users = manager_group.users

                if not manager_users:
                    _logger.warning('No manager users found in group_shuttle_manager - skipping daily summary')
                    return True

                # Get email template
                try:
                    template = self.env.ref('shuttlebee.email_template_daily_summary')
                except Exception as e:
                    _logger.error(f"Email template 'shuttlebee.email_template_daily_summary' not found: {str(e)}")
                    return True

                # Send email to each manager
                sent_count = 0
                error_count = 0

                for user in manager_users:
                    try:
                        if not user.email:
                            _logger.warning(f"Manager user {user.name} (ID: {user.id}) has no email - skipping")
                            error_count += 1
                            continue

                        template.with_context(
                            user=user,
                            total_trips=total_trips,
                            total_passengers=total_passengers,
                            total_present=total_present,
                            total_absent=total_absent,
                            attendance_rate=attendance_rate,
                            today=today
                        ).send_mail(user.id, force_send=True)
                        sent_count += 1
                        _logger.debug(f"Daily summary sent to manager {user.name} ({user.email})")

                    except Exception as e:
                        error_count += 1
                        _logger.error(
                            f"Failed to send daily summary to manager {user.name} (ID: {user.id}): {str(e)}",
                            exc_info=True
                        )

                _logger.info(
                    f"Daily summary cron completed: {sent_count} sent, {error_count} errors "
                    f"for {total_trips} trips on {today}"
                )

            except Exception as e:
                _logger.error(
                    f"Error getting manager group or users for daily summary: {str(e)}",
                    exc_info=True
                )

        except Exception as e:
            _logger.error(
                f"Critical error in _cron_send_daily_summary: {str(e)}",
                exc_info=True
            )
            # Don't raise - allow cron to continue

        return True

    @api.model
    def _expand_states(self, states, domain, order):
        """Expand states for kanban group_by"""
        return [key for key, val in type(self).state.selection]

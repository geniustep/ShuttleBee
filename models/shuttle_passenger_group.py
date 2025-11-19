# -*- coding: utf-8 -*-

import logging
import math
from datetime import datetime, timedelta, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from pytz import timezone as pytz_timezone, UTC

from .shuttle_passenger_group_schedule import WEEKDAY_SELECTION, WEEKDAY_TO_INT

_logger = logging.getLogger(__name__)


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
    use_company_destination = fields.Boolean(
        string='Use Company Destination',
        default=True,
        help='When enabled, the company GPS coordinates will be used as the destination '
             'location for passengers who do not have specific stops.'
    )
    destination_latitude = fields.Float(
        string='Destination Latitude',
        digits=(10, 7),
        default=lambda self: self.env.company.shuttle_latitude
    )
    destination_longitude = fields.Float(
        string='Destination Longitude',
        digits=(10, 7),
        default=lambda self: self.env.company.shuttle_longitude
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
    schedule_ids = fields.One2many(
        'shuttle.passenger.group.schedule',
        'group_id',
        string='Weekly Schedule',
        copy=True
    )
    holiday_ids = fields.One2many(
        'shuttle.passenger.group.holiday',
        'group_id',
        string='Holidays / Exceptions',
        copy=True
    )
    auto_schedule_enabled = fields.Boolean(
        string='Auto Generate Weekly Trips',
        default=True,
        help='If enabled, a weekly cron will automatically generate trips for this group.'
    )
    auto_schedule_weeks = fields.Integer(
        string='Weeks to Generate',
        default=1,
        help='Number of weeks to generate automatically (starting next Monday).'
    )
    auto_schedule_include_pickup = fields.Boolean(
        string='Include Pickup in Auto Schedule',
        default=True
    )
    auto_schedule_include_dropoff = fields.Boolean(
        string='Include Dropoff in Auto Schedule',
        default=True
    )
    schedule_timezone = fields.Char(
        string='Schedule Timezone',
        help='Timezone used to interpret pickup/dropoff times for this group. '
             'Defaults to the company shuttle timezone.',
        default='UTC'
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

    @api.model_create_multi
    def create(self, vals_list):
        shuttle_vehicle_model = self.env['shuttle.vehicle']
        company_model = self.env['res.company']
        for vals in vals_list:
            if vals.get('vehicle_id'):
                vehicle = shuttle_vehicle_model.browse(vals['vehicle_id'])
                if vehicle:
                    vals.setdefault('driver_id', vehicle.driver_id.id)
                    if vehicle.seat_capacity:
                        vals.setdefault('total_seats', vehicle.seat_capacity)
            use_company_dest = vals.get('use_company_destination', True)
            if use_company_dest:
                company = company_model.browse(vals['company_id']) if vals.get('company_id') else self.env.company
                if company:
                    vals.setdefault('destination_latitude', company.shuttle_latitude)
                    vals.setdefault('destination_longitude', company.shuttle_longitude)
            if not vals.get('schedule_timezone'):
                company = company_model.browse(vals['company_id']) if vals.get('company_id') else self.env.company
                vals.setdefault(
                    'schedule_timezone',
                    company.shuttle_schedule_timezone
                    or company.partner_id.tz
                    or self.env.user.tz
                    or 'UTC'
                )
            if not vals.get('schedule_ids'):
                vals['schedule_ids'] = self._prepare_default_schedule_vals(company_id=vals.get('company_id'))
        return super().create(vals_list)

    def _prepare_default_schedule_vals(self, company_id=None):
        """Generate default Monday-Friday schedule entries."""
        from datetime import datetime, time
        today = fields.Date.today()
        default_pickup = fields.Datetime.to_string(datetime.combine(today, time(7, 0)))
        default_dropoff = fields.Datetime.to_string(datetime.combine(today, time(14, 45)))
        working_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        schedule_vals = []
        for weekday in (key for key, _label in WEEKDAY_SELECTION):
            active = weekday in working_days
            schedule_vals.append((0, 0, {
                'weekday': weekday,
                'pickup_time': default_pickup,
                'dropoff_time': default_dropoff,
                'create_pickup': True,
                'create_dropoff': True,
                'active': active,
            }))
        return schedule_vals

    def write(self, vals):
        res = super().write(vals)
        if 'use_company_destination' in vals or 'company_id' in vals:
            for group in self:
                if group.use_company_destination:
                    company = group.company_id or self.env.company
                    updates = {
                        'destination_stop_id': False,
                        'destination_latitude': company.shuttle_latitude,
                        'destination_longitude': company.shuttle_longitude,
                    }
                    super(ShuttlePassengerGroup, group).write(updates)
        return res

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

        use_company_destination = (
            self.use_company_destination and
            self.destination_latitude and
            self.destination_longitude
        )
        line_vals = []
        for line in self.line_ids:
            if not line.passenger_id:
                continue
            passenger = line.passenger_id

            # Respect passenger direction preference
            direction = passenger.shuttle_trip_direction or 'both'
            if trip_type == 'pickup' and direction == 'dropoff':
                continue
            if trip_type == 'dropoff' and direction == 'pickup':
                continue

            # Initialize vals - will be set based on trip_type
            vals = {
                'group_line_id': line.id,
                'passenger_id': passenger.id,
                'pickup_stop_id': False,  # Will be set based on trip_type
                'dropoff_stop_id': False,  # Will be set based on trip_type
                'seat_count': line.seat_count or 1,
                'notes': line.notes,
            }
            
            # Use destination_stop_id if passenger doesn't have a stop for the trip direction
            if trip_type == 'pickup':
                # For pickup trips:
                # - pickup location = passenger home (from line.pickup_stop_id or passenger GPS)
                # - dropoff location = school/work (from line.dropoff_stop_id or company destination)
                if line.pickup_stop_id:
                    vals['pickup_stop_id'] = line.pickup_stop_id.id
                if line.dropoff_stop_id:
                    vals['dropoff_stop_id'] = line.dropoff_stop_id.id
                # For pickup trips: destination is dropoff (school/work)
                if not vals['dropoff_stop_id']:
                    if self.destination_stop_id:
                        vals['dropoff_stop_id'] = self.destination_stop_id.id
                    elif use_company_destination:
                        vals['dropoff_latitude'] = self.destination_latitude
                        vals['dropoff_longitude'] = self.destination_longitude
            elif trip_type == 'dropoff':
                # For dropoff trips: 
                # - pickup location = school/work (company destination)
                # - dropoff location = passenger home (from line.pickup_stop_id or passenger GPS)
                
                # Set pickup location (company/school)
                company_pickup_stop_id = None
                if not vals['pickup_stop_id']:
                    if self.destination_stop_id:
                        company_pickup_stop_id = self.destination_stop_id.id
                        vals['pickup_stop_id'] = company_pickup_stop_id
                    elif use_company_destination:
                        vals['pickup_latitude'] = self.destination_latitude
                        vals['pickup_longitude'] = self.destination_longitude
                
                # Dropoff location for dropoff trips = passenger home
                # Use pickup_stop_id from line (if passenger has a pickup stop) or passenger GPS
                # But make sure it's different from pickup_stop_id (company)
                if not vals['dropoff_stop_id']:
                    # Use the pickup stop from line as dropoff location (passenger's home)
                    if line.pickup_stop_id and line.pickup_stop_id.id != company_pickup_stop_id:
                        vals['dropoff_stop_id'] = line.pickup_stop_id.id
                    elif passenger.shuttle_latitude and passenger.shuttle_longitude:
                        vals['dropoff_latitude'] = passenger.shuttle_latitude
                        vals['dropoff_longitude'] = passenger.shuttle_longitude
                else:
                    # If dropoff_stop_id is already set from line, check if it's same as pickup
                    if company_pickup_stop_id and vals.get('dropoff_stop_id') == company_pickup_stop_id:
                        # If same as company, clear dropoff_stop_id and use GPS instead
                        vals['dropoff_stop_id'] = False
                        if line.pickup_stop_id and line.pickup_stop_id.id != company_pickup_stop_id:
                            vals['dropoff_stop_id'] = line.pickup_stop_id.id
                        elif passenger.shuttle_latitude and passenger.shuttle_longitude:
                            vals['dropoff_latitude'] = passenger.shuttle_latitude
                            vals['dropoff_longitude'] = passenger.shuttle_longitude
            
            # Only add trip_id if provided (for actual creation, not onchange)
            if trip_id:
                vals['trip_id'] = trip_id
            
            # For pickup trips: pickup location = passenger home
            if trip_type == 'pickup':
                # If no pickup stop but passenger has coordinates, use them
                if not vals['pickup_stop_id'] and passenger.shuttle_latitude and passenger.shuttle_longitude:
                    vals['pickup_latitude'] = passenger.shuttle_latitude
                    vals['pickup_longitude'] = passenger.shuttle_longitude
            
            line_vals.append(vals)
        return line_vals

    def action_open_schedule_generate_wizard(self):
        self.ensure_one()
        return {
            'name': _('Generate Trips from Schedule'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.group.schedule.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_group_id': self.id,
                'default_start_date': fields.Date.context_today(self),
            }
        }

    def generate_trips_from_schedule(
        self,
        start_date,
        weeks=1,
        include_pickup=True,
        include_dropoff=True,
        limit_to_week=False,
    ):
        self.ensure_one()
        if not start_date:
            raise UserError(_('Please provide a start date.'))
        if weeks <= 0:
            raise UserError(_('Number of weeks must be greater than zero.'))
        if not self.driver_id:
            raise UserError(_('Assign a driver to the passenger group before generating trips.'))

        schedule_lines = self.schedule_ids.filtered('active')
        if not schedule_lines:
            raise UserError(_('No active schedule lines found. Configure the weekly schedule first.'))
        active_holidays = self.holiday_ids.filtered('active')

        start_dt = fields.Date.to_date(start_date)
        created_trips = self.env['shuttle.trip']
        total_days = weeks * 7
        if limit_to_week:
            days_remaining = 7 - start_dt.weekday()
            total_days = min(total_days, days_remaining)

        for offset in range(total_days):
            current_date = start_dt + timedelta(days=offset)
            weekday_int = current_date.weekday()
            day_lines = schedule_lines.filtered(
                lambda l: WEEKDAY_TO_INT.get(l.weekday) == weekday_int
            )
            if not day_lines:
                continue
            # Skip if date inside holiday
            if active_holidays.filtered(lambda h: h.start_date <= current_date <= h.end_date):
                continue
            for line in day_lines:
                if include_pickup and line.create_pickup and line.pickup_time:
                    trip = self._create_trip_from_schedule(
                        current_date=current_date,
                        schedule_line=line,
                        trip_type='pickup',
                        schedule_datetime=line.pickup_time
                    )
                    created_trips |= trip
                if include_dropoff and line.create_dropoff and line.dropoff_time:
                    trip = self._create_trip_from_schedule(
                        current_date=current_date,
                        schedule_line=line,
                        trip_type='dropoff',
                        schedule_datetime=line.dropoff_time
                    )
                    created_trips |= trip

        if not created_trips:
            raise UserError(_('No trips were created. Check schedule settings and avoid duplicates.'))

        return {
            'name': _('Scheduled Trips'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.trip',
            'view_mode': 'list,form,kanban,calendar',
            'domain': [('id', 'in', created_trips.ids)],
        }

    def _create_trip_from_schedule(self, current_date, schedule_line, trip_type, schedule_datetime):
        dt_value = self._combine_date_and_datetime(current_date, schedule_datetime)
        Trip = self.env['shuttle.trip']
        existing_trip = Trip.search([
            ('group_id', '=', self.id),
            ('date', '=', current_date),
            ('trip_type', '=', trip_type),
            ('planned_start_time', '=', dt_value),
        ], limit=1)
        if existing_trip:
            return existing_trip

        # Check for vehicle conflict before creating trip
        if self.vehicle_id:
            # Calculate estimated end time (default 2 hours if no dropoff time)
            if trip_type == 'pickup' and schedule_line.dropoff_time:
                end_dt_value = self._combine_date_and_datetime(current_date, schedule_line.dropoff_time)
            else:
                # Default 2 hours duration
                start_dt = fields.Datetime.from_string(dt_value) if isinstance(dt_value, str) else dt_value
                end_dt_value = start_dt + timedelta(hours=2)
            
            # Check for overlapping trips with same vehicle
            start_dt = fields.Datetime.from_string(dt_value) if isinstance(dt_value, str) else dt_value
            end_dt = fields.Datetime.from_string(end_dt_value) if isinstance(end_dt_value, str) else end_dt_value
            
            conflicting = Trip.search([
                ('id', '!=', False),  # Will be replaced by existing_trip.id if exists
                ('vehicle_id', '=', self.vehicle_id.id),
                ('date', '=', current_date),
                ('state', 'not in', ['draft', 'cancelled']),
            ])
            
            for conflict in conflicting:
                conflict_start = conflict.planned_start_time
                conflict_end = conflict.planned_arrival_time or (conflict_start + timedelta(hours=2))
                
                # Check if time ranges overlap
                if start_dt < conflict_end and end_dt > conflict_start:
                    _logger.warning(
                        'Vehicle conflict detected when generating trip from schedule: '
                        'Vehicle %s already used in trip %s (%s - %s). '
                        'Skipping trip creation for %s on %s.',
                        self.vehicle_id.name,
                        conflict.name,
                        conflict_start,
                        conflict_end,
                        self.name,
                        current_date
                    )
                    # Skip this trip instead of raising error (to allow other trips to be created)
                    return Trip.browse()  # Return empty recordset

        trip_name = '%s - %s - %s' % (
            self.name,
            current_date.strftime('%Y-%m-%d'),
            'Pickup' if trip_type == 'pickup' else 'Dropoff'
        )
        trip_vals = {
            'name': trip_name,
            'trip_type': trip_type,
            'driver_id': self.driver_id.id,
            'vehicle_id': self.vehicle_id.id,
            'group_id': self.id,
            'date': current_date,
            'planned_start_time': dt_value,
            'total_seats': self.total_seats,
            'company_id': self.company_id.id,
            'state': 'draft',
        }
        trip = Trip.create(trip_vals)
        line_vals = self._prepare_trip_line_values(trip_id=trip.id, trip_type=trip_type)
        if line_vals:
            self.env['shuttle.trip.line'].create(line_vals)
        return trip

    def _combine_date_and_datetime(self, date_value, schedule_datetime):
        """Combine trip date with schedule datetime (extract time from schedule_datetime)"""
        if not schedule_datetime:
            raise ValueError('schedule_datetime is required')
        
        # Extract time from schedule_datetime
        schedule_dt = fields.Datetime.from_string(schedule_datetime) if isinstance(schedule_datetime, str) else schedule_datetime
        schedule_time = schedule_dt.time()
        
        # Combine with trip date
        naive_dt = datetime.combine(date_value, schedule_time)

        tz_name = (
            self.schedule_timezone
            or self.company_id.shuttle_schedule_timezone
            or self.company_id.partner_id.tz
            or self.env.context.get('tz')
            or self.env.user.tz
            or 'UTC'
        )
        tz = pytz_timezone(tz_name)
        localized = tz.localize(naive_dt, is_dst=None)
        utc_dt = localized.astimezone(UTC)
        # Return naive UTC datetime string (Odoo stores datetimes as naive UTC)
        return fields.Datetime.to_string(utc_dt.replace(tzinfo=None))

    @api.model
    def cron_generate_weekly_trips(self):
        """Generate next week's trips every Saturday morning."""
        today = fields.Date.context_today(self)
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)

        groups = self.search([('auto_schedule_enabled', '=', True)])
        for group in groups:
            try:
                weeks = group.auto_schedule_weeks or 1
                group.generate_trips_from_schedule(
                    start_date=next_monday,
                    weeks=weeks,
                    include_pickup=group.auto_schedule_include_pickup,
                    include_dropoff=group.auto_schedule_include_dropoff,
                    limit_to_week=False,
                )
            except Exception as exc:
                _logger.exception(
                    'Failed to auto-generate trips for group %s (%s): %s',
                    group.name, group.id, exc
                )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id:
            if self.vehicle_id.driver_id:
                self.driver_id = self.vehicle_id.driver_id
            if self.vehicle_id.seat_capacity:
                self.total_seats = self.vehicle_id.seat_capacity
    
    @api.constrains('vehicle_id')
    def _check_vehicle_conflict_in_group(self):
        """Warn if vehicle is already assigned to another active group on same schedule"""
        for group in self:
            if not group.vehicle_id:
                continue
            
            # Check if vehicle is used in other groups with overlapping schedules
            other_groups = self.search([
                ('id', '!=', group.id),
                ('vehicle_id', '=', group.vehicle_id.id),
                ('active', '=', True),
            ])
            
            if other_groups:
                # Log warning but don't block (groups can share vehicles if schedules don't overlap)
                _logger.info(
                    'Vehicle %s is assigned to multiple groups: %s and %s. '
                    'Ensure schedules do not overlap.',
                    group.vehicle_id.name,
                    group.name,
                    ', '.join(other_groups.mapped('name'))
                )

    @api.onchange('use_company_destination', 'company_id')
    def _onchange_use_company_destination(self):
        if self.use_company_destination and self.company_id:
            self.destination_stop_id = False
            self.destination_latitude = self.company_id.shuttle_latitude
            self.destination_longitude = self.company_id.shuttle_longitude


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
    pickup_info_display = fields.Char(
        string='Pickup Details',
        compute='_compute_location_displays',
        store=True,
        help='Readable pickup information showing either the stop name or the passenger address.'
    )
    dropoff_info_display = fields.Char(
        string='Dropoff Details',
        compute='_compute_location_displays',
        store=True,
        help='Readable dropoff information showing either the stop name or the passenger address.'
    )

    _sql_constraints = [
        ('unique_passenger_per_group',
         'unique(group_id, passenger_id)',
         'Passenger already exists in this group.'),
        ('positive_seat_requirement', 'CHECK(seat_count > 0)',
         'Seat count must be positive.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Load default pickup/dropoff stops from passenger settings when creating"""
        for vals in vals_list:
            if 'passenger_id' in vals and vals['passenger_id']:
                passenger = self.env['res.partner'].browse(vals['passenger_id'])
                if passenger.exists():
                    # Load default pickup stop if passenger has one and no override is set
                    if 'pickup_stop_id' not in vals or not vals.get('pickup_stop_id'):
                        if passenger.default_pickup_stop_id:
                            vals['pickup_stop_id'] = passenger.default_pickup_stop_id.id
                    
                    # Load default dropoff stop if passenger has one and no override is set
                    if 'dropoff_stop_id' not in vals or not vals.get('dropoff_stop_id'):
                        if passenger.default_dropoff_stop_id:
                            vals['dropoff_stop_id'] = passenger.default_dropoff_stop_id.id
        
        return super().create(vals_list)

    @api.depends(
        'pickup_stop_id',
        'pickup_stop_id.name',
        'dropoff_stop_id',
        'dropoff_stop_id.name',
        'passenger_id',
        'passenger_id.name',
        'passenger_id.contact_address',
        'passenger_id.shuttle_latitude',
        'passenger_id.shuttle_longitude',
        'passenger_id.use_gps_for_dropoff',
        'passenger_id.default_pickup_stop_id',
        'passenger_id.default_dropoff_stop_id',
        'group_id',
        'group_id.company_id',
        'group_id.company_id.name',
        'group_id.company_id.street',
        'group_id.company_id.city',
        'group_id.company_id.shuttle_latitude',
        'group_id.company_id.shuttle_longitude'
    )
    def _compute_location_displays(self):
        for line in self:
            pickup_stop = line.pickup_stop_id
            dropoff_stop = line.dropoff_stop_id
            
            line.pickup_info_display = line._format_location_display(
                stop=pickup_stop,
                passenger=line.passenger_id,
                is_dropoff=False
            )
            line.dropoff_info_display = line._format_location_display(
                stop=dropoff_stop,
                passenger=line.passenger_id,
                is_dropoff=True,
                group=line.group_id
            )

    def _format_location_display(self, stop, passenger, is_dropoff=False, group=None):
        # Check if stop exists and has a valid ID
        if stop and stop.id:
            return stop.display_name or stop.name or _('Stop #%s') % stop.id
        
        if not passenger:
            return _('No passenger selected')

        # For dropoff, check if using company GPS coordinates
        if is_dropoff:
            # Check if passenger uses company GPS for dropoff
            if passenger.use_gps_for_dropoff and group:
                company = group.company_id or self.env.company
                if company:
                    # Return company name and address
                    company_parts = [company.name or _('Company')]
                    if company.street:
                        company_parts.append(company.street)
                    if company.city:
                        company_parts.append(company.city)
                    if company_parts:
                        return ' - '.join(company_parts)
                    # Fallback to company name with GPS if available
                    if company.shuttle_latitude and company.shuttle_longitude:
                        return '%s - GPS: %s / %s' % (
                            company.name or _('Company'),
                            company.shuttle_latitude,
                            company.shuttle_longitude
                        )
                    return company.name or _('Company')

        # For pickup or when not using company GPS, show passenger info
        parts = [passenger.display_name or passenger.name]
        address = passenger.contact_address
        if address:
            parts.append(address)
        elif passenger.shuttle_latitude and passenger.shuttle_longitude:
            parts.append(_('GPS: %(lat)s / %(lng)s') % {
                'lat': passenger.shuttle_latitude,
                'lng': passenger.shuttle_longitude,
            })
        else:
            parts.append(_('No address specified'))
        return ' - '.join(parts)

    @api.onchange('passenger_id')
    def _onchange_passenger_id(self):
        """Load default pickup/dropoff stops from passenger settings"""
        if not self.passenger_id:
            return
        
        passenger = self.passenger_id
        
        # Load default pickup stop if passenger has one and no override is set
        if not self.pickup_stop_id and passenger.default_pickup_stop_id:
            self.pickup_stop_id = passenger.default_pickup_stop_id
        
        # Load default dropoff stop if passenger has one and no override is set
        if not self.dropoff_stop_id and passenger.default_dropoff_stop_id:
            self.dropoff_stop_id = passenger.default_dropoff_stop_id
        
        # Recompute displays
        self._compute_location_displays()

    @api.onchange('pickup_stop_id')
    def _onchange_pickup_stop_id(self):
        """Force recompute of pickup_info_display when pickup_stop_id changes"""
        self._compute_location_displays()

    @api.onchange('dropoff_stop_id')
    def _onchange_dropoff_stop_id(self):
        """Force recompute of dropoff_info_display when dropoff_stop_id changes"""
        self._compute_location_displays()

    def action_recompute_location_displays(self):
        """Recompute location displays for all lines in the group"""
        self.ensure_one()
        if self.line_ids:
            self.line_ids._compute_location_displays()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Location displays have been recomputed.'),
                    'type': 'success',
                }
            }

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


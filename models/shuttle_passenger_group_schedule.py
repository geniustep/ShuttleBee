# -*- coding: utf-8 -*-

from datetime import datetime, time
from pytz import timezone as pytz_timezone, UTC
from odoo import api, fields, models, _


# Use plain strings at module level to avoid translation warnings
# The _() function will be called at runtime in selection fields
WEEKDAY_SELECTION = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
]

WEEKDAY_TO_INT = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
    'saturday': 5,
    'sunday': 6,
}


class ShuttlePassengerGroupSchedule(models.Model):
    _name = 'shuttle.passenger.group.schedule'
    _description = 'Passenger Group Weekly Schedule'
    _order = 'weekday'

    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Group',
        required=True,
        ondelete='cascade'
    )
    weekday = fields.Selection(
        selection=WEEKDAY_SELECTION,
        string='Weekday',
        required=True,
        default='monday'
    )
    pickup_time = fields.Datetime(
        string='Pickup Time',
        help='Default pickup start time for this weekday.'
    )
    dropoff_time = fields.Datetime(
        string='Dropoff Time',
        help='Default dropoff start time for this weekday.'
    )
    pickup_time_display = fields.Char(
        string='Pickup Time',
        compute='_compute_time_display',
        store=False,
        help='Display pickup time as HH:MM'
    )
    dropoff_time_display = fields.Char(
        string='Dropoff Time',
        compute='_compute_time_display',
        store=False,
        help='Display dropoff time as HH:MM'
    )
    
    @api.depends('pickup_time', 'dropoff_time')
    def _compute_time_display(self):
        for record in self:
            if record.pickup_time:
                # Convert UTC datetime to user timezone
                dt_utc = fields.Datetime.from_string(record.pickup_time)
                dt_local = fields.Datetime.context_timestamp(record, dt_utc)
                record.pickup_time_display = dt_local.strftime('%H:%M')
            else:
                record.pickup_time_display = ''
            
            if record.dropoff_time:
                # Convert UTC datetime to user timezone
                dt_utc = fields.Datetime.from_string(record.dropoff_time)
                dt_local = fields.Datetime.context_timestamp(record, dt_utc)
                record.dropoff_time_display = dt_local.strftime('%H:%M')
            else:
                record.dropoff_time_display = ''
                
    create_pickup = fields.Boolean(
        string='Create Pickup',
        default=True,
        help='Generate pickup trip for this day.'
    )
    create_dropoff = fields.Boolean(
        string='Create Dropoff',
        default=True,
        help='Generate dropoff trip for this day.'
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        related='group_id.company_id',
        store=True,
        readonly=True
    )

    _sql_constraints = [
        ('unique_group_weekday',
         'unique(group_id, weekday)',
         'Weekday already configured for this passenger group.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Convert Float values to Datetime if needed, respecting timezone.
        Also check if a record with the same group_id and weekday exists (even if inactive)
        and activate it instead of creating a duplicate."""
        records_to_create = []
        records_to_activate = []
        
        for vals in vals_list:
            group_id = vals.get('group_id')
            weekday = vals.get('weekday')
            
            # Check if a record already exists (even if inactive) for this group and weekday
            if group_id and weekday:
                existing = self.search([
                    ('group_id', '=', group_id),
                    ('weekday', '=', weekday)
                ], limit=1)
                
                if existing:
                    # Instead of creating a new record, update the existing one
                    update_vals = vals.copy()
                    # Remove group_id and weekday from update_vals as they shouldn't change
                    update_vals.pop('group_id', None)
                    update_vals.pop('weekday', None)
                    
                    # Process time values if needed
                    update_vals = self._process_time_values(update_vals, group_id)
                    
                    # Activate the record and update it
                    update_vals['active'] = True
                    existing.write(update_vals)
                    records_to_activate.append(existing)
                    continue
            
            # Process time values for new records
            vals = self._process_time_values(vals, group_id)
            records_to_create.append(vals)
        
        # Create only new records that don't have duplicates
        result = self.browse()
        if records_to_create:
            result = super().create(records_to_create)
        
        # Return all records (newly created + reactivated)
        if records_to_activate:
            result = result | self.browse([r.id for r in records_to_activate])
        
        return result
    
    def _process_time_values(self, vals, group_id=None):
        """Process and convert time values from Float/string to Datetime if needed"""
        # Get timezone from group if available
        tz_name = 'UTC'
        if group_id:
            group = self.env['shuttle.passenger.group'].browse(group_id)
            if group.exists():
                tz_name = (
                    group.schedule_timezone
                    or group.company_id.shuttle_schedule_timezone
                    or group.company_id.partner_id.tz
                    or self.env.context.get('tz')
                    or self.env.user.tz
                    or 'UTC'
                )
        else:
            tz_name = (
                self.env.context.get('tz')
                or self.env.user.tz
                or 'UTC'
            )
        
        tz = pytz_timezone(tz_name)
        
        # Convert pickup_time from Float/string to Datetime if needed
        if 'pickup_time' in vals and vals['pickup_time']:
            pickup_val = vals['pickup_time']
            if isinstance(pickup_val, (int, float)) or (isinstance(pickup_val, str) and pickup_val.replace('.', '', 1).isdigit()):
                try:
                    float_val = float(pickup_val)
                    hours = int(float_val)
                    minutes = int(round((float_val - hours) * 60))
                    today = fields.Date.today()
                    # Create naive datetime in local timezone
                    naive_dt = datetime.combine(today, time(hours, minutes))
                    # Localize to user timezone
                    local_dt = tz.localize(naive_dt)
                    # Convert to UTC for storage
                    utc_dt = local_dt.astimezone(UTC)
                    vals['pickup_time'] = fields.Datetime.to_string(utc_dt.replace(tzinfo=None))
                except (ValueError, TypeError):
                    pass
        
        # Convert dropoff_time from Float/string to Datetime if needed
        if 'dropoff_time' in vals and vals['dropoff_time']:
            dropoff_val = vals['dropoff_time']
            if isinstance(dropoff_val, (int, float)) or (isinstance(dropoff_val, str) and dropoff_val.replace('.', '', 1).isdigit()):
                try:
                    float_val = float(dropoff_val)
                    hours = int(float_val)
                    minutes = int(round((float_val - hours) * 60))
                    today = fields.Date.today()
                    # Create naive datetime in local timezone
                    naive_dt = datetime.combine(today, time(hours, minutes))
                    # Localize to user timezone
                    local_dt = tz.localize(naive_dt)
                    # Convert to UTC for storage
                    utc_dt = local_dt.astimezone(UTC)
                    vals['dropoff_time'] = fields.Datetime.to_string(utc_dt.replace(tzinfo=None))
                except (ValueError, TypeError):
                    pass
        
        return vals

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'group_id' in res:
            group = self.env['shuttle.passenger.group'].browse(res['group_id'])
            if group.company_id:
                res['company_id'] = group.company_id.id
        return res


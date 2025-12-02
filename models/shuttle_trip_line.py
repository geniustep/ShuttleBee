# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

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
        domain=[('stop_type', 'in', ['pickup', 'both'])],
        ondelete='restrict'
    )
    dropoff_stop_id = fields.Many2one(
        'shuttle.stop',
        string='Dropoff Stop',
        domain=[('stop_type', 'in', ['dropoff', 'both'])],
        ondelete='restrict'
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
    ], string='Status', default='planned', required=True, index=True)

    # Sequence
    sequence = fields.Integer(
        string='Stop Sequence',
        default=10,
        help='Order of pickup/dropoff in the trip'
    )

    boarding_time = fields.Datetime(
        string='Boarding Time',
        readonly=True,
        copy=False
    )
    absence_reason = fields.Char(
        string='Absence Reason',
        help='Optional reason provided when marking the passenger absent.'
    )
    is_billable = fields.Boolean(
        string='Billable',
        default=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='trip_id.company_id.currency_id',
        store=True,
        readonly=True
    )
    price = fields.Monetary(
        string='Price',
        currency_field='currency_id',
        help='Optional price for this passenger on this trip.'
    )
    invoice_line_id = fields.Many2one(
        'account.move.line',
        string='Invoice Line',
        readonly=True,
        ondelete='set null'
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
    def _ensure_trip_state(self, allowed_states, action_label):
        """Ensure trip is in an allowed state before changing passenger status"""
        state_labels = dict(self.env['shuttle.trip']._fields['state'].selection)
        for line in self:
            if line.trip_id and line.trip_id.state not in allowed_states:
                raise UserError(_(
                    'Cannot %s while trip "%s" is in state %s.'
                ) % (action_label, line.trip_id.name, state_labels.get(line.trip_id.state, line.trip_id.state)))

    def _service_response(self, updates):
        """Return structured data for API consumers when requested"""
        if self.env.context.get('service_response'):
            return {
                'updated_count': len(updates),
                'details': updates,
            }
        return True

    def action_mark_boarded(self):
        """Mark passenger as boarded, and mark all other passengers who are not absent as boarded"""
        self._ensure_trip_state(['ongoing'], _('mark passenger as boarded'))
        updates = []
        trip = None
        
        for line in self:
            if not trip:
                trip = line.trip_id
            
            previous_status = line.status
            if previous_status != 'boarded':
                line.write({
                    'status': 'boarded',
                    'boarding_time': fields.Datetime.now(),
                    'absence_reason': False,
                })
            line.trip_id.message_post(
                body=_('Passenger %s has boarded.') % line.passenger_id.name
            )
            updates.append({
                'trip_line_id': line.id,
                'trip_id': line.trip_id.id,
                'previous_status': previous_status,
                'new_status': line.status,
            })
        
        # Mark all other passengers who are not absent as boarded
        if trip:
            marked_count = 0
            for line in trip.line_ids:
                if line.id not in self.ids and line.status != 'absent' and line.status != 'boarded':
                    previous_status = line.status
                    line.write({
                        'status': 'boarded',
                        'boarding_time': fields.Datetime.now() if not line.boarding_time else line.boarding_time,
                    })
                    updates.append({
                        'trip_line_id': line.id,
                        'trip_id': line.trip_id.id,
                        'previous_status': previous_status,
                        'new_status': line.status,
                    })
                    marked_count += 1
            
            if marked_count > 0:
                trip.message_post(
                    body=_('Automatically marked %s other passenger(s) as boarded.') % marked_count
                )
        
        return self._service_response(updates)

    def action_mark_absent(self):
        """Mark passenger as absent"""
        self._ensure_trip_state(['planned', 'ongoing'], _('mark passenger as absent'))
        updates = []
        reason = self.env.context.get('absence_reason')
        for line in self:
            previous_status = line.status
            if previous_status != 'absent':
                vals = {
                    'status': 'absent',
                    'boarding_time': False,
                }
                if reason:
                    vals['absence_reason'] = reason
                line.write(vals)
            line.trip_id.message_post(
                body=_('Passenger %s marked as absent.') % line.passenger_id.name
            )
            updates.append({
                'trip_line_id': line.id,
                'trip_id': line.trip_id.id,
                'previous_status': previous_status,
                'new_status': line.status,
            })
        return self._service_response(updates)

    def action_mark_dropped(self):
        """Mark passenger as dropped off"""
        self._ensure_trip_state(['ongoing'], _('mark passenger as dropped off'))
        updates = []
        for line in self:
            previous_status = line.status
            if previous_status != 'dropped':
                line.write({
                    'status': 'dropped',
                    'absence_reason': False,
                })
            line.trip_id.message_post(
                body=_('Passenger %s dropped off.') % line.passenger_id.name
            )
            updates.append({
                'trip_line_id': line.id,
                'trip_id': line.trip_id.id,
                'previous_status': previous_status,
                'new_status': line.status,
            })
        return self._service_response(updates)

    def action_reset_to_planned(self):
        """Reset passenger status back to planned"""
        self._ensure_trip_state(['planned', 'ongoing'], _('reset passenger to planned'))
        updates = []
        for line in self:
            previous_status = line.status
            if previous_status != 'planned':
                line.write({
                    'status': 'planned',
                    'boarding_time': False,
                    'absence_reason': False,
                })
            line.trip_id.message_post(
                body=_('Passenger %s status reset to planned.') % line.passenger_id.name
            )
            updates.append({
                'trip_line_id': line.id,
                'trip_id': line.trip_id.id,
                'previous_status': previous_status,
                'new_status': line.status,
            })
        return self._service_response(updates)

    def _get_notification_template_values(self):
        """Get values for message template rendering"""
        self.ensure_one()
        trip = self.trip_id
        passenger = self.passenger_id
        driver = trip.driver_id
        vehicle = trip.vehicle_id
        company = trip.company_id or self.env.company
        
        # Format trip time from planned_start_time
        trip_time = ''
        if trip.planned_start_time:
            trip_time = trip.planned_start_time.strftime('%H:%M')
        
        return {
            'passenger_name': passenger.name or '',
            'driver_name': driver.name if driver else '',
            'vehicle_name': vehicle.name if vehicle else '',
            'vehicle_plate': vehicle.license_plate if vehicle else '',
            'stop_name': self.pickup_stop_id.name if self.pickup_stop_id else _('your location'),
            'trip_name': trip.name or '',
            'trip_date': str(trip.date) if trip.date else '',
            'trip_time': trip_time,
            'eta': '10',
            'company_name': company.name or '',
            'company_phone': company.phone or '',
        }

    def action_send_approaching_notification(self):
        """Send approaching notification using customizable templates"""
        MessageTemplate = self.env['shuttle.message.template']
        
        for line in self:
            # Get default notification channel from settings
            default_channel = self.env['ir.config_parameter'].sudo().get_param(
                'shuttlebee.notification_channel', 'whatsapp'
            )
            
            # Get passenger language preference (default to Arabic)
            language = getattr(line.passenger_id, 'lang', 'ar_001') or 'ar'
            if language.startswith('ar'):
                language = 'ar'
            elif language.startswith('en'):
                language = 'en'
            elif language.startswith('fr'):
                language = 'fr'
            else:
                language = 'ar'
            
            # Get template
            template = MessageTemplate.get_template(
                notification_type='approaching',
                channel=default_channel,
                language=language,
                company=line.trip_id.company_id
            )
            
            # Prepare template values
            values = line._get_notification_template_values()
            
            # Render message
            if template:
                message_content = template.render_message(values)
            else:
                # Fallback message
                message_content = _(
                    'Hello %s, Driver %s is approaching pickup point %s. ETA: 10 minutes.'
                ) % (values['passenger_name'], values['driver_name'], values['stop_name'])

            self.env['shuttle.notification'].create({
                'trip_id': line.trip_id.id,
                'trip_line_id': line.id,
                'passenger_id': line.passenger_id.id,
                'notification_type': 'approaching',
                'channel': default_channel,
                'message_content': message_content,
                'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
            })._send_notification()

            line.write({
                'status': 'notified_approaching',
                'approaching_notified': True
            })
        return True

    def action_send_arrived_notification(self):
        """Send arrived notification using customizable templates"""
        MessageTemplate = self.env['shuttle.message.template']
        
        for line in self:
            # Get default notification channel from settings
            default_channel = self.env['ir.config_parameter'].sudo().get_param(
                'shuttlebee.notification_channel', 'whatsapp'
            )
            
            # Get passenger language preference
            language = getattr(line.passenger_id, 'lang', 'ar_001') or 'ar'
            if language.startswith('ar'):
                language = 'ar'
            elif language.startswith('en'):
                language = 'en'
            elif language.startswith('fr'):
                language = 'fr'
            else:
                language = 'ar'
            
            # Get template
            template = MessageTemplate.get_template(
                notification_type='arrived',
                channel=default_channel,
                language=language,
                company=line.trip_id.company_id
            )
            
            # Prepare template values
            values = line._get_notification_template_values()
            
            # Render message
            if template:
                message_content = template.render_message(values)
            else:
                # Fallback message
                message_content = _(
                    'Dear %s, Driver %s has arrived at %s. Please head to the shuttle immediately!'
                ) % (values['passenger_name'], values['driver_name'], values['stop_name'])

            self.env['shuttle.notification'].create({
                'trip_id': line.trip_id.id,
                'trip_line_id': line.id,
                'passenger_id': line.passenger_id.id,
                'notification_type': 'arrived',
                'channel': default_channel,
                'message_content': message_content,
                'recipient_phone': line.passenger_id.phone or line.passenger_id.mobile,
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
                    self.pickup_latitude = False
                    self.pickup_longitude = False
                if group_line[0].dropoff_stop_id:
                    self.dropoff_stop_id = group_line[0].dropoff_stop_id
                    self.dropoff_latitude = False
                    self.dropoff_longitude = False
                if group_line[0].seat_count:
                    self.seat_count = group_line[0].seat_count
            else:
                # If passenger not in group, use defaults from passenger
                self._apply_passenger_defaults()
        elif self.passenger_id:
            # Set defaults from passenger
            self._apply_passenger_defaults()
    
    def _apply_passenger_defaults(self):
        """Apply passenger default pickup and dropoff settings"""
        if not self.passenger_id:
            return
        
        passenger = self.passenger_id
        company = self.trip_id.company_id if self.trip_id else self.env.company
        
        # Pickup: Use GPS if enabled and no override stop, otherwise use override stop
        if passenger.use_gps_for_pickup and not passenger.default_pickup_stop_id:
            # Use passenger GPS coordinates for pickup
            if passenger.shuttle_latitude and passenger.shuttle_longitude:
                self.pickup_stop_id = False
                self.pickup_latitude = passenger.shuttle_latitude
                self.pickup_longitude = passenger.shuttle_longitude
        elif passenger.default_pickup_stop_id:
            # Use override stop
            self.pickup_stop_id = passenger.default_pickup_stop_id
            self.pickup_latitude = False
            self.pickup_longitude = False
        elif passenger.shuttle_latitude and passenger.shuttle_longitude:
            # Fallback: use GPS if available
            self.pickup_stop_id = False
            self.pickup_latitude = passenger.shuttle_latitude
            self.pickup_longitude = passenger.shuttle_longitude
        
        # Dropoff: Use company GPS if enabled and no override stop, otherwise use override stop
        if passenger.use_gps_for_dropoff and not passenger.default_dropoff_stop_id:
            # Use company GPS coordinates for dropoff
            if company and company.shuttle_latitude and company.shuttle_longitude:
                self.dropoff_stop_id = False
                self.dropoff_latitude = company.shuttle_latitude
                self.dropoff_longitude = company.shuttle_longitude
        elif passenger.default_dropoff_stop_id:
            # Use override stop
            self.dropoff_stop_id = passenger.default_dropoff_stop_id
            self.dropoff_latitude = False
            self.dropoff_longitude = False
        elif company and company.shuttle_latitude and company.shuttle_longitude:
            # Fallback: use company GPS if available
            self.dropoff_stop_id = False
            self.dropoff_latitude = company.shuttle_latitude
            self.dropoff_longitude = company.shuttle_longitude
        elif passenger.shuttle_latitude and passenger.shuttle_longitude:
            # Fallback: use passenger GPS if company GPS not available
            self.dropoff_stop_id = False
            self.dropoff_latitude = passenger.shuttle_latitude
            self.dropoff_longitude = passenger.shuttle_longitude

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

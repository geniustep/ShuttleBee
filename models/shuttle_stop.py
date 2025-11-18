# -*- coding: utf-8 -*-

import math

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ShuttleStop(models.Model):
    _name = 'shuttle.stop'
    _description = 'Shuttle Stop (Pickup/Dropoff Point)'
    _order = 'sequence, name'

    # Basic Info
    name = fields.Char(
        string='Stop Name',
        required=True,
        translate=True,
        index=True
    )
    code = fields.Char(
        string='Stop Code',
        copy=False
    )

    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')

    # GPS Coordinates
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7)
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7)
    )

    # Type & Status
    stop_type = fields.Selection([
        ('pickup', 'Pickup Only'),
        ('dropoff', 'Dropoff Only'),
        ('both', 'Pickup & Dropoff')
    ], string='Stop Type', required=True, default='both')
    active = fields.Boolean(string='Active', default=True)

    # Display
    color = fields.Integer(string='Color', default=0)
    sequence = fields.Integer(string='Sequence', default=10)

    # Statistics (computed)
    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count',
        store=True
    )

    # Additional
    notes = fields.Text(string='Notes', translate=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True
    )

    # Constraints
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for stop in self:
            if stop.latitude and not (-90 <= stop.latitude <= 90):
                raise ValidationError(_('Latitude must be between -90 and 90!'))
            if stop.longitude and not (-180 <= stop.longitude <= 180):
                raise ValidationError(_('Longitude must be between -180 and 180!'))

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Stop code must be unique!'),
    ]

    # Computed Methods
    @api.depends('pickup_line_ids', 'dropoff_line_ids')
    def _compute_usage_count(self):
        for stop in self:
            pickup_count = len(stop.pickup_line_ids)
            dropoff_count = len(stop.dropoff_line_ids)
            stop.usage_count = pickup_count + dropoff_count

    # Relations (for usage computation)
    pickup_line_ids = fields.One2many(
        'shuttle.trip.line',
        'pickup_stop_id',
        string='Pickup Lines'
    )
    dropoff_line_ids = fields.One2many(
        'shuttle.trip.line',
        'dropoff_stop_id',
        string='Dropoff Lines'
    )

    # Methods
    def name_get(self):
        """Custom display name"""
        result = []
        for stop in self:
            name = stop.name
            if stop.code:
                name = f"[{stop.code}] {name}"
            if stop.city:
                name = f"{name} - {stop.city}"
            result.append((stop.id, name))
        return result

    @api.model
    def create(self, vals):
        """Generate code if not provided"""
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('shuttle.stop') or 'STOP'
        return super().create(vals)

    def action_view_usage(self):
        """View trips using this stop"""
        self.ensure_one()
        return {
            'name': _('Stop Usage'),
            'type': 'ir.actions.act_window',
            'res_model': 'shuttle.trip.line',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('pickup_stop_id', '=', self.id),
                ('dropoff_stop_id', '=', self.id)
            ],
        }

    # Service Methods
    @api.model
    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance in kilometers between two points"""
        if None in (lat1, lon1, lat2, lon2):
            return None

        # Earth radius in kilometers
        R = 6371.0

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    @api.model
    def suggest_nearest(self, latitude, longitude, limit=1, stop_type=None, company_id=None):
        """Return the nearest active stops for given coordinates"""
        if latitude is None or longitude is None:
            raise UserError(_('Latitude and longitude are required to find nearest stops.'))

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            raise ValidationError(_('Invalid latitude or longitude value.'))

        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            raise ValidationError(_('Latitude must be between -90 and 90, and longitude between -180 and 180.'))

        domain = [('active', '=', True)]
        if stop_type:
            if stop_type not in ['pickup', 'dropoff', 'both']:
                raise ValidationError(_('Invalid stop_type value.'))
            domain.append(('stop_type', 'in', ['both', stop_type]))

        if company_id:
            company = self.env['res.company'].browse(company_id)
            if not company.exists():
                raise UserError(_('Company not found.'))
            domain.append(('company_id', '=', company.id))

        stops = self.search(domain)
        if not stops:
            return []

        suggestions = []
        for stop in stops:
            distance = self._haversine_distance(latitude, longitude, stop.latitude, stop.longitude)
            if distance is None:
                continue
            suggestions.append({
                'stop_id': stop.id,
                'name': stop.name,
                'distance_km': round(distance, 3),
                'stop_type': stop.stop_type,
            })

        suggestions.sort(key=lambda s: s['distance_km'])
        limit = int(limit) if limit else 1
        return suggestions[:limit]

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ShuttleGpsPosition(models.Model):
    _name = 'shuttle.gps.position'
    _description = 'Shuttle GPS Position'
    _order = 'timestamp desc'
    _rec_name = 'timestamp'

    trip_id = fields.Many2one(
        'shuttle.trip',
        string='Trip',
        required=True,
        ondelete='cascade',
        index=True
    )
    vehicle_id = fields.Many2one(
        'shuttle.vehicle',
        string='Vehicle',
        ondelete='set null',
        index=True
    )
    driver_id = fields.Many2one(
        'res.users',
        string='Driver',
        ondelete='set null',
        index=True
    )
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        required=True
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        required=True
    )
    speed = fields.Float(
        string='Speed (km/h)'
    )
    heading = fields.Float(
        string='Heading (°)'
    )
    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    company_id = fields.Many2one(
        related='trip_id.company_id',
        store=True,
        readonly=True,
        index=True
    )

    _sql_constraints = [
        ('gps_coordinates_range',
         'CHECK(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)',
         'Latitude must be between -90 and 90, and longitude between -180 and 180.')
    ]

    @api.model
    def create(self, vals):
        self._validate_coordinates(vals.get('latitude'), vals.get('longitude'))
        return super().create(vals)

    def write(self, vals):
        if 'latitude' in vals or 'longitude' in vals:
            lat = vals.get('latitude', self.latitude)
            lon = vals.get('longitude', self.longitude)
            self._validate_coordinates(lat, lon)
        return super().write(vals)

    def _validate_coordinates(self, latitude, longitude):
        if latitude is None or longitude is None:
            raise ValidationError(_('Latitude and longitude are required.'))
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValidationError(_('Latitude must be between -90 and 90, and longitude between -180 and 180.'))


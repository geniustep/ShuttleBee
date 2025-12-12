# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ShuttleVehiclePosition(models.Model):
    """
    Vehicle/driver heartbeat positions even when no trip is ongoing.
    Used for rare security cases: identify the driver precisely even if all trips are draft.
    """
    _name = 'shuttle.vehicle.position'
    _description = 'Shuttle Vehicle Position (Heartbeat)'
    _order = 'timestamp desc'

    vehicle_id = fields.Many2one('shuttle.vehicle', string='Vehicle', required=True, index=True, ondelete='cascade')
    driver_id = fields.Many2one('res.users', string='Driver', required=True, index=True, ondelete='cascade')
    latitude = fields.Float(string='Latitude', digits=(10, 7), required=True)
    longitude = fields.Float(string='Longitude', digits=(10, 7), required=True)
    speed = fields.Float(string='Speed (km/h)')
    heading = fields.Float(string='Heading (°)')
    accuracy = fields.Float(string='Accuracy (m)')
    timestamp = fields.Datetime(string='Timestamp', required=True, default=fields.Datetime.now, index=True)
    note = fields.Char(string='Note', help='Small message to display on map marker.')
    company_id = fields.Many2one(related='vehicle_id.company_id', store=True, readonly=True, index=True)

    _sql_constraints = [
        ('pos_coordinates_range',
         'CHECK(latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)',
         'Latitude must be between -90 and 90, and longitude between -180 and 180.')
    ]

    @api.constrains('latitude', 'longitude')
    def _check_coords(self):
        for rec in self:
            if rec.latitude is None or rec.longitude is None:
                raise ValidationError(_('Latitude and longitude are required.'))
            if not (-90 <= rec.latitude <= 90 and -180 <= rec.longitude <= 180):
                raise ValidationError(_('Latitude must be between -90 and 90, and longitude between -180 and 180.'))



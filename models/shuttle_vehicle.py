# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ShuttleVehicle(models.Model):
    _name = 'shuttle.vehicle'
    _description = 'Shuttle Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Vehicle Name', required=True, tracking=True, translate=True)
    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Fleet Vehicle',
        required=True,
        ondelete='restrict',
        tracking=True
    )
    license_plate = fields.Char(
        string='License Plate',
        related='fleet_vehicle_id.license_plate',
        store=True,
        readonly=True
    )
    seat_capacity = fields.Integer(
        string='Seat Capacity',
        default=12,
        required=True,
        tracking=True
    )
    driver_id = fields.Many2one(
        'res.users',
        string='Default Driver',
        tracking=True
    )
    # Vehicle Home/Parking Location (Starting Point)
    home_latitude = fields.Float(
        string='Parking Latitude',
        digits=(10, 7),
        tracking=True,
        help='GPS latitude of vehicle parking/home location (starting point for trips)'
    )
    home_longitude = fields.Float(
        string='Parking Longitude',
        digits=(10, 7),
        tracking=True,
        help='GPS longitude of vehicle parking/home location (starting point for trips)'
    )
    home_address = fields.Char(
        string='Parking Address',
        tracking=True,
        help='Physical address of vehicle parking location'
    )
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes', translate=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True
    )
    trip_ids = fields.One2many(
        'shuttle.trip',
        'vehicle_id',
        string='Trips'
    )

    _sql_constraints = [
        ('shuttle_vehicle_unique_fleet', 'unique(fleet_vehicle_id)',
         'Fleet vehicle is already linked to another shuttle vehicle.'),
        ('shuttle_vehicle_positive_capacity', 'CHECK(seat_capacity > 0)',
         'Seat capacity must be positive.'),
    ]

    @api.constrains('seat_capacity')
    def _check_seat_capacity(self):
        for vehicle in self:
            if vehicle.seat_capacity <= 0:
                raise ValidationError(_('Seat capacity must be greater than zero.'))

    @api.constrains('home_latitude', 'home_longitude')
    def _check_home_coordinates(self):
        """Validate vehicle home/parking GPS coordinates"""
        for vehicle in self:
            if vehicle.home_latitude and not (-90 <= vehicle.home_latitude <= 90):
                raise ValidationError(_('Parking latitude must be between -90 and 90.'))
            if vehicle.home_longitude and not (-180 <= vehicle.home_longitude <= 180):
                raise ValidationError(_('Parking longitude must be between -180 and 180.'))

    @api.onchange('fleet_vehicle_id')
    def _onchange_fleet_vehicle_id(self):
        if self.fleet_vehicle_id:
            self.license_plate = self.fleet_vehicle_id.license_plate
            if self.fleet_vehicle_id.driver_id:
                self.driver_id = self.fleet_vehicle_id.driver_id.user_id or self.driver_id
            if self.fleet_vehicle_id.seats and not self.seat_capacity:
                self.seat_capacity = self.fleet_vehicle_id.seats


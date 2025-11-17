# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ShuttleVehicle(models.Model):
    _name = 'shuttle.vehicle'
    _description = 'Shuttle Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Vehicle Name', required=True, tracking=True)
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
    color = fields.Integer(string='Color Index')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
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

    @api.onchange('fleet_vehicle_id')
    def _onchange_fleet_vehicle_id(self):
        if self.fleet_vehicle_id:
            self.license_plate = self.fleet_vehicle_id.license_plate
            if self.fleet_vehicle_id.driver_id:
                self.driver_id = self.fleet_vehicle_id.driver_id.user_id or self.driver_id
            if self.fleet_vehicle_id.seats and not self.seat_capacity:
                self.seat_capacity = self.fleet_vehicle_id.seats


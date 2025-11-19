# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    # GPS Coordinates for Company Location (used as default dropoff location)
    shuttle_latitude = fields.Float(
        string='Company Latitude',
        digits=(10, 7),
        help='GPS latitude for company location (used as default dropoff location for passengers)'
    )
    shuttle_longitude = fields.Float(
        string='Company Longitude',
        digits=(10, 7),
        help='GPS longitude for company location (used as default dropoff location for passengers)'
    )

    shuttle_schedule_timezone = fields.Char(
        string='Shuttle Schedule Timezone',
        help='Default timezone used to interpret shuttle schedules when creating trips.',
        default=lambda self: self.env.user.tz or 'UTC'
    )


# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShuttleGroupScheduleGenerateWizard(models.TransientModel):
    _name = 'shuttle.group.schedule.generate.wizard'
    _description = 'Generate Trips from Passenger Group Schedule'

    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Passenger Group',
        required=True
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=lambda self: fields.Date.context_today(self)
    )
    weeks = fields.Integer(
        string='Number of Weeks',
        default=1,
        help='Number of weeks to generate trips for (starting from Start Date).'
    )
    include_pickup = fields.Boolean(
        string='Include Pickup Trips',
        default=True
    )
    include_dropoff = fields.Boolean(
        string='Include Dropoff Trips',
        default=True
    )
    limit_to_week = fields.Boolean(
        string='Limit to Current Week',
        default=True,
        help='When enabled, only generate trips up to the end of the current week.'
    )

    def action_generate(self):
        self.ensure_one()
        if self.weeks <= 0:
            raise UserError(_('Number of weeks must be greater than zero.'))
        if not self.include_pickup and not self.include_dropoff:
            raise UserError(_('Select at least one trip direction to generate.'))
        return self.group_id.generate_trips_from_schedule(
            start_date=self.start_date,
            weeks=self.weeks,
            include_pickup=self.include_pickup,
            include_dropoff=self.include_dropoff,
            limit_to_week=self.limit_to_week,
        )


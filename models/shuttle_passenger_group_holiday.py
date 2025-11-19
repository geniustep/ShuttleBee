# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ShuttlePassengerGroupHoliday(models.Model):
    _name = 'shuttle.passenger.group.holiday'
    _description = 'Passenger Group Holiday'
    _order = 'start_date'

    group_id = fields.Many2one(
        'shuttle.passenger.group',
        string='Passenger Group',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='Reason',
        required=True,
        default=lambda self: _('Holiday')
    )
    start_date = fields.Date(
        string='Start Date',
        required=True
    )
    end_date = fields.Date(
        string='End Date',
        required=True
    )
    company_id = fields.Many2one(
        'res.company',
        related='group_id.company_id',
        store=True,
        readonly=True
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('check_date_range', 'CHECK(end_date >= start_date)',
         'End date must be after start date.'),
    ]

    def includes_date(self, target_date):
        self.ensure_one()
        if not self.active:
            return False
        return self.start_date <= target_date <= self.end_date


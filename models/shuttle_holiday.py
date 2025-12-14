# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ShuttleHoliday(models.Model):
    _name = 'shuttle.holiday'
    _description = 'Shuttle Holiday (Global)'
    _order = 'start_date'

    name = fields.Char(
        string='Reason',
        required=True,
        default=lambda self: _('Holiday'),
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
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


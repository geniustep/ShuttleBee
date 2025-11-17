# -*- coding: utf-8 -*-

from odoo import models


class ShuttleTripReport(models.AbstractModel):
    _name = 'report.shuttlebee.report_shuttle_trip_document'
    _description = 'Shuttle Trip Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['shuttle.trip'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'shuttle.trip',
            'docs': docs,
            'data': data,
        }

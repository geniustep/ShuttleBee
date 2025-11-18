# -*- coding: utf-8 -*-

from odoo import api, models


class ShuttleConfigHelper(models.AbstractModel):
    _name = 'shuttle.config.helper'
    _description = 'Shuttle Configuration Helper'

    def _selection_to_dict(self, model, field_name):
        """Return the selection field values/labels as a dictionary"""
        field = model._fields.get(field_name)
        if not field or not field.selection:
            return {}
        if callable(field.selection):
            selection = field.selection(model)
        else:
            selection = field.selection
        return dict(selection or [])

    @api.model
    def get_enums(self):
        """Return all selection enums used across shuttle models"""
        Trip = self.env['shuttle.trip']
        TripLine = self.env['shuttle.trip.line']
        Stop = self.env['shuttle.stop']
        Notification = self.env['shuttle.notification']

        enums = {
            'trip_states': self._selection_to_dict(Trip, 'state'),
            'trip_types': self._selection_to_dict(Trip, 'trip_type'),
            'trip_line_statuses': self._selection_to_dict(TripLine, 'status'),
            'stop_types': self._selection_to_dict(Stop, 'stop_type'),
            'notification_types': self._selection_to_dict(Notification, 'notification_type'),
            'notification_channels': self._selection_to_dict(Notification, 'channel'),
        }
        return enums


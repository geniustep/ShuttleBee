# -*- coding: utf-8 -*-
"""
Conflict detection utilities for vehicle and driver scheduling
Optimized database-level conflict checking to avoid N+1 queries
"""

import logging
from datetime import timedelta
from typing import List, Dict, Any, Optional, Tuple
from odoo import fields, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ConflictDetector:
    """
    Centralized conflict detection for vehicle and driver assignments
    Uses database-level queries for better performance
    """

    def __init__(self, trip_model):
        """
        Initialize conflict detector

        Args:
            trip_model: Reference to shuttle.trip model
        """
        self.trip_model = trip_model

    def check_vehicle_conflict(
        self,
        vehicle_id: int,
        trip_date,
        start_time,
        end_time,
        exclude_trip_id: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check for vehicle conflicts using optimized database query

        Args:
            vehicle_id: Vehicle ID to check
            trip_date: Date of the trip
            start_time: Trip start datetime
            end_time: Trip end datetime (or None)
            exclude_trip_id: Trip ID to exclude from check (for updates)

        Returns:
            Tuple[bool, Optional[Dict]]: (has_conflict, conflict_data)
        """
        if not vehicle_id or not start_time:
            return False, None

        # Ensure datetime objects
        start_dt = fields.Datetime.to_datetime(start_time)
        if not start_dt:
            return False, None

        # Default 2 hours if no end time
        end_dt = fields.Datetime.to_datetime(end_time) if end_time else (start_dt + timedelta(hours=2))

        # Build domain for conflicting trips
        domain = [
            ('vehicle_id', '=', vehicle_id),
            ('date', '=', trip_date),
            ('state', '!=', 'cancelled'),  # Include draft, planned, ongoing, done
            ('planned_start_time', '!=', False),
        ]

        if exclude_trip_id:
            domain.append(('id', '!=', exclude_trip_id))

        # Find potentially conflicting trips
        conflicting_trips = self.trip_model.search(domain)

        for conflict in conflicting_trips:
            conflict_start = fields.Datetime.to_datetime(conflict.planned_start_time)
            if not conflict_start:
                continue

            conflict_end = (
                fields.Datetime.to_datetime(conflict.planned_arrival_time)
                if conflict.planned_arrival_time
                else (conflict_start + timedelta(hours=2))
            )

            # Check if time ranges overlap
            if self._times_overlap(start_dt, end_dt, conflict_start, conflict_end):
                return True, {
                    'trip_id': conflict.id,
                    'trip_name': conflict.name,
                    'start_time': conflict_start,
                    'end_time': conflict_end,
                    'group_name': conflict.group_id.name if conflict.group_id else _('N/A'),
                    'state': conflict.state,
                    'vehicle_name': conflict.vehicle_id.name,
                }

        return False, None

    def check_driver_conflict(
        self,
        driver_id: int,
        trip_date,
        start_time,
        end_time,
        exclude_trip_id: Optional[int] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check for driver conflicts using optimized database query

        Args:
            driver_id: Driver user ID to check
            trip_date: Date of the trip
            start_time: Trip start datetime
            end_time: Trip end datetime (or None)
            exclude_trip_id: Trip ID to exclude from check (for updates)

        Returns:
            Tuple[bool, Optional[Dict]]: (has_conflict, conflict_data)
        """
        if not driver_id or not start_time:
            return False, None

        # Ensure datetime objects
        start_dt = fields.Datetime.to_datetime(start_time)
        if not start_dt:
            return False, None

        # Default 2 hours if no end time
        end_dt = fields.Datetime.to_datetime(end_time) if end_time else (start_dt + timedelta(hours=2))

        # Build domain for conflicting trips
        domain = [
            ('driver_id', '=', driver_id),
            ('date', '=', trip_date),
            ('state', '!=', 'cancelled'),  # Include draft, planned, ongoing, done
            ('planned_start_time', '!=', False),
        ]

        if exclude_trip_id:
            domain.append(('id', '!=', exclude_trip_id))

        # Find potentially conflicting trips
        conflicting_trips = self.trip_model.search(domain)

        for conflict in conflicting_trips:
            conflict_start = fields.Datetime.to_datetime(conflict.planned_start_time)
            if not conflict_start:
                continue

            conflict_end = (
                fields.Datetime.to_datetime(conflict.planned_arrival_time)
                if conflict.planned_arrival_time
                else (conflict_start + timedelta(hours=2))
            )

            # Check if time ranges overlap
            if self._times_overlap(start_dt, end_dt, conflict_start, conflict_end):
                return True, {
                    'trip_id': conflict.id,
                    'trip_name': conflict.name,
                    'start_time': conflict_start,
                    'end_time': conflict_end,
                    'group_name': conflict.group_id.name if conflict.group_id else _('N/A'),
                    'vehicle_name': conflict.vehicle_id.name if conflict.vehicle_id else _('N/A'),
                    'state': conflict.state,
                    'driver_name': conflict.driver_id.name,
                }

        return False, None

    def check_all_conflicts(
        self,
        vehicle_id: Optional[int],
        driver_id: Optional[int],
        trip_date,
        start_time,
        end_time,
        exclude_trip_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Check both vehicle and driver conflicts

        Args:
            vehicle_id: Vehicle ID to check (optional)
            driver_id: Driver user ID to check (optional)
            trip_date: Date of the trip
            start_time: Trip start datetime
            end_time: Trip end datetime (or None)
            exclude_trip_id: Trip ID to exclude from check (for updates)

        Returns:
            Dict with conflict information

        Raises:
            ValidationError: If conflicts are found
        """
        results = {
            'has_vehicle_conflict': False,
            'has_driver_conflict': False,
            'vehicle_conflict': None,
            'driver_conflict': None,
        }

        # Check vehicle conflict
        if vehicle_id:
            has_conflict, conflict_data = self.check_vehicle_conflict(
                vehicle_id, trip_date, start_time, end_time, exclude_trip_id
            )
            results['has_vehicle_conflict'] = has_conflict
            results['vehicle_conflict'] = conflict_data

            if has_conflict:
                raise ValidationError(self._format_vehicle_conflict_message(conflict_data))

        # Check driver conflict
        if driver_id:
            has_conflict, conflict_data = self.check_driver_conflict(
                driver_id, trip_date, start_time, end_time, exclude_trip_id
            )
            results['has_driver_conflict'] = has_conflict
            results['driver_conflict'] = conflict_data

            if has_conflict:
                raise ValidationError(self._format_driver_conflict_message(conflict_data))

        return results

    @staticmethod
    def _times_overlap(start1, end1, start2, end2) -> bool:
        """
        Check if two time ranges overlap

        Args:
            start1: First range start
            end1: First range end
            start2: Second range start
            end2: Second range end

        Returns:
            bool: True if ranges overlap
        """
        return start1 < end2 and end1 > start2

    @staticmethod
    def _format_vehicle_conflict_message(conflict_data: Dict[str, Any]) -> str:
        """Format vehicle conflict error message"""
        state_label = dict([
            ('draft', _('Draft')),
            ('planned', _('Planned')),
            ('ongoing', _('Ongoing')),
            ('done', _('Done')),
            ('cancelled', _('Cancelled'))
        ]).get(conflict_data['state'], conflict_data['state'])

        return _(
            'Vehicle conflict detected!\n\n'
            'Vehicle "%(vehicle)s" is already assigned to another trip:\n'
            '• Trip: %(trip)s\n'
            '• Time: %(start)s - %(end)s\n'
            '• Group: %(group)s\n'
            '• Status: %(status)s\n\n'
            'Please choose a different vehicle or adjust the trip time.'
        ) % {
            'vehicle': conflict_data['vehicle_name'],
            'trip': conflict_data['trip_name'],
            'start': conflict_data['start_time'].strftime('%Y-%m-%d %H:%M'),
            'end': conflict_data['end_time'].strftime('%H:%M'),
            'group': conflict_data['group_name'],
            'status': state_label
        }

    @staticmethod
    def _format_driver_conflict_message(conflict_data: Dict[str, Any]) -> str:
        """Format driver conflict error message"""
        state_label = dict([
            ('draft', _('Draft')),
            ('planned', _('Planned')),
            ('ongoing', _('Ongoing')),
            ('done', _('Done')),
            ('cancelled', _('Cancelled'))
        ]).get(conflict_data['state'], conflict_data['state'])

        return _(
            'Driver conflict detected!\n\n'
            'Driver "%(driver)s" is already assigned to another trip:\n'
            '• Trip: %(trip)s\n'
            '• Time: %(start)s - %(end)s\n'
            '• Group: %(group)s\n'
            '• Vehicle: %(vehicle)s\n'
            '• Status: %(status)s\n\n'
            'Please choose a different driver or adjust the trip time.'
        ) % {
            'driver': conflict_data['driver_name'],
            'trip': conflict_data['trip_name'],
            'start': conflict_data['start_time'].strftime('%Y-%m-%d %H:%M'),
            'end': conflict_data['end_time'].strftime('%H:%M'),
            'group': conflict_data['group_name'],
            'vehicle': conflict_data['vehicle_name'],
            'status': state_label
        }

    def validate_trip_conflicts(
        self,
        trip_record,
        check_vehicle: bool = True,
        check_driver: bool = True
    ):
        """
        Validate conflicts for a trip record

        Args:
            trip_record: shuttle.trip record
            check_vehicle: Whether to check vehicle conflicts
            check_driver: Whether to check driver conflicts

        Raises:
            ValidationError: If conflicts are found
        """
        # Skip cancelled trips
        if trip_record.state == 'cancelled':
            return

        if not trip_record.planned_start_time:
            return

        vehicle_id = trip_record.vehicle_id.id if check_vehicle and trip_record.vehicle_id else None
        driver_id = trip_record.driver_id.id if check_driver and trip_record.driver_id else None

        if not vehicle_id and not driver_id:
            return

        self.check_all_conflicts(
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            trip_date=trip_record.date,
            start_time=trip_record.planned_start_time,
            end_time=trip_record.planned_arrival_time,
            exclude_trip_id=trip_record.id
        )

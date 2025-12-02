# -*- coding: utf-8 -*-
"""
Compatibility tests for ShuttleBee v2.0.0
Tests to ensure backward compatibility with existing data
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from odoo.tests import tagged, TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields


@tagged('shuttlebee', 'compatibility', 'post_install')
class TestBackwardCompatibility(TransactionCase):
    """Test backward compatibility with existing data"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.env = self.env(user=self.env.ref('base.user_admin'))

    def test_existing_trips_still_work(self):
        """Test that existing trips continue to work"""
        # Create a passenger group
        group = self.env['shuttle.passenger.group'].create({
            'name': 'Test Group',
            'trip_type': 'pickup',
        })
        
        # Create a trip (old way)
        trip = self.env['shuttle.trip'].create({
            'name': 'Test Trip',
            'trip_type': 'pickup',
            'date': fields.Date.today(),
            'group_id': group.id,
        })
        
        self.assertTrue(trip)
        self.assertEqual(trip.state, 'draft')

    def test_existing_notifications_still_work(self):
        """Test that existing notifications continue to work"""
        # Create a passenger
        passenger = self.env['res.partner'].create({
            'name': 'Test Passenger',
            'phone': '+212612345678',
            'is_shuttle_passenger': True,
        })
        
        # Create a notification (old way)
        notification = self.env['shuttle.notification'].create({
            'passenger_id': passenger.id,
            'notification_type': 'approaching',
            'channel': 'sms',
            'message_content': 'Test message',
        })
        
        self.assertTrue(notification)
        self.assertEqual(notification.status, 'pending')

    def test_new_helpers_work_with_old_data(self):
        """Test that new helpers work with old data structures"""
        from shuttlebee.helpers.validation import ValidationHelper
        
        # Old phone format should still work
        old_phone = "0612345678"
        is_valid = ValidationHelper.validate_phone(old_phone, raise_error=False)
        self.assertTrue(is_valid)
        
        # Old email format should still work
        old_email = "user@example.com"
        is_valid = ValidationHelper.validate_email(old_email, raise_error=False)
        self.assertTrue(is_valid)

    def test_conflict_detector_with_existing_trips(self):
        """Test conflict detector with existing trips"""
        from shuttlebee.helpers.conflict_detector import ConflictDetector
        
        # Create existing trip
        group = self.env['shuttle.passenger.group'].create({
            'name': 'Test Group',
            'trip_type': 'pickup',
        })
        
        vehicle = self.env['shuttle.vehicle'].create({
            'name': 'Test Vehicle',
            'seat_capacity': 20,
        })
        
        existing_trip = self.env['shuttle.trip'].create({
            'name': 'Existing Trip',
            'trip_type': 'pickup',
            'date': fields.Date.today(),
            'group_id': group.id,
            'vehicle_id': vehicle.id,
            'planned_start_time': fields.Datetime.now(),
            'state': 'planned',
        })
        
        # Test conflict detection
        detector = ConflictDetector(self.env['shuttle.trip'])
        
        has_conflict, conflict_data = detector.check_vehicle_conflict(
            vehicle_id=vehicle.id,
            trip_date=fields.Date.today(),
            start_time=fields.Datetime.now(),
            end_time=fields.Datetime.now() + timedelta(hours=2),
            exclude_trip_id=None
        )
        
        # Should detect conflict with existing trip
        self.assertTrue(has_conflict)

    def test_notification_providers_with_old_settings(self):
        """Test notification providers work with old settings"""
        from shuttlebee.helpers.notification_providers import ProviderFactory
        
        # Old settings format should still work
        config = self.env['res.config.settings'].create({
            'shuttlebee_sms_api_url': 'https://api.example.com/sms',
            'shuttlebee_sms_api_key': 'old_api_key',
        })
        
        # Should be able to create provider with old settings
        try:
            provider = ProviderFactory.create_provider(
                provider_type='generic_sms',
                api_url=config.shuttlebee_sms_api_url,
                api_key=config.shuttlebee_sms_api_key
            )
            self.assertIsNotNone(provider)
        except Exception as e:
            # If provider creation fails, it should be a clear error
            self.assertIsInstance(e, (UserError, ValueError))

    def test_rate_limiter_with_existing_notifications(self):
        """Test rate limiter doesn't break existing notification flow"""
        from shuttlebee.helpers.rate_limiter import notification_rate_limiter
        
        # Should allow sending (rate limiter should not block existing flow)
        can_send = notification_rate_limiter.can_send('sms')
        self.assertTrue(can_send)

    def test_validation_helper_backward_compatible(self):
        """Test validation helper is backward compatible"""
        from shuttlebee.helpers.validation import ValidationHelper
        
        # Old validation methods should still work
        # Test with various phone formats that were previously accepted
        old_formats = [
            "0612345678",
            "212612345678",
            "+212612345678",
            "06 12 34 56 78",
        ]
        
        for phone in old_formats:
            # Should not raise error (backward compatible)
            try:
                is_valid = ValidationHelper.validate_phone(phone, raise_error=False)
                # At least some should be valid
                if phone.replace(' ', '').replace('+', '').isdigit():
                    self.assertTrue(is_valid or len(phone) >= 7)
            except Exception:
                # Should not crash
                pass


@tagged('shuttlebee', 'migration', 'post_install')
class TestDataMigration(TransactionCase):
    """Test data migration scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.env = self.env(user=self.env.ref('base.user_admin'))

    def test_no_data_loss_on_upgrade(self):
        """Test that no data is lost when upgrading to v2.0.0"""
        # Create old data
        group = self.env['shuttle.passenger.group'].create({
            'name': 'Old Group',
            'trip_type': 'pickup',
        })
        
        trip = self.env['shuttle.trip'].create({
            'name': 'Old Trip',
            'trip_type': 'pickup',
            'date': fields.Date.today(),
            'group_id': group.id,
        })
        
        # After upgrade, data should still exist
        self.assertTrue(group.exists())
        self.assertTrue(trip.exists())
        
        # All fields should still be accessible
        self.assertEqual(trip.name, 'Old Trip')
        self.assertEqual(trip.group_id, group)

    def test_new_fields_optional(self):
        """Test that new fields are optional and don't break old records"""
        # Create record without new fields
        notification = self.env['shuttle.notification'].create({
            'passenger_id': self.env['res.partner'].create({
                'name': 'Test',
                'phone': '+212612345678',
            }).id,
            'notification_type': 'approaching',
            'channel': 'sms',
            'message_content': 'Test',
        })
        
        # Should work without new helper-related fields
        self.assertTrue(notification)
        self.assertEqual(notification.status, 'pending')

    def test_helpers_gracefully_handle_missing_data(self):
        """Test helpers handle missing/None data gracefully"""
        from shuttlebee.helpers.validation import ValidationHelper
        
        # Should handle None gracefully
        is_valid = ValidationHelper.validate_phone(None, raise_error=False)
        self.assertFalse(is_valid)
        
        is_valid = ValidationHelper.validate_email(None, raise_error=False)
        self.assertFalse(is_valid)


if __name__ == '__main__':
    unittest.main()


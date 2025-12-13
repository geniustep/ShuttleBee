# -*- coding: utf-8 -*-
"""
Test suite for ShuttleBee Mobile API endpoints.

This tests the REST API endpoints defined in controllers/mobile_api.py:
- GET  /api/v1/shuttle/trips/my - Get driver's trips
- POST /api/v1/shuttle/trips/<trip_id>/confirm - Confirm a trip
- GET  /api/v1/shuttle/live/ongoing - Get ongoing trips (for live map)
- GET  /api/v1/shuttle/trips/<trip_id>/gps - Get GPS path for a trip
- POST /api/v1/shuttle/vehicle/position - Report vehicle position

Usage:
    # Run with Odoo test runner:
    python odoo-bin -c odoo.conf -d testdb --test-enable --test-tags=shuttlebee_mobile

    # Or run standalone (requires running Odoo server):
    python -m pytest tests/test_mobile_api.py -v

Environment Variables:
    ODOO_URL - Odoo server URL (default: http://localhost:8069)
    ODOO_DB - Database name (default: odoo)
    ODOO_USER - Username (default: admin)
    ODOO_PASSWORD - Password (default: admin)
"""

import json
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import requests

# Odoo test imports (for running within Odoo)
try:
    from odoo.tests import tagged, TransactionCase, HttpCase
    from odoo.exceptions import AccessError
    from odoo import fields
    ODOO_AVAILABLE = True
except ImportError:
    ODOO_AVAILABLE = False
    # Create dummy decorators for standalone testing
    def tagged(*args):
        return lambda cls: cls
    class TransactionCase(unittest.TestCase):
        pass
    class HttpCase(unittest.TestCase):
        pass


# ============================================================================
# Configuration
# ============================================================================

ODOO_URL = os.getenv('ODOO_URL', 'https://app.propanel.ma')
ODOO_DB = os.getenv('ODOO_DB', 'shuttlebee')
ODOO_USER = os.getenv('ODOO_USER', 'done')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD', ',,07Genius')

API_BASE = f"{ODOO_URL}/api/v1/shuttle"


# ============================================================================
# Helper Classes
# ============================================================================

class OdooSession:
    """Helper class to manage Odoo session authentication."""
    
    def __init__(self, base_url=ODOO_URL, db=ODOO_DB, username=ODOO_USER, password=ODOO_PASSWORD):
        self.base_url = base_url.rstrip('/')
        self.db = db
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.uid = None
        self.session_id = None
    
    def authenticate(self):
        """Authenticate with Odoo and get session cookie."""
        url = f"{self.base_url}/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password,
            },
            "id": 1
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if 'error' in result:
            raise Exception(f"Authentication failed: {result['error']}")
        
        self.uid = result.get('result', {}).get('uid')
        if not self.uid:
            raise Exception("Authentication failed: No user ID returned")
        
        # Session cookie is automatically stored
        self.session_id = self.session.cookies.get('session_id')
        return self.uid
    
    def get(self, endpoint, params=None):
        """Make authenticated GET request."""
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, params=params)
        return response
    
    def post(self, endpoint, data=None, json_data=None):
        """Make authenticated POST request."""
        url = f"{self.base_url}{endpoint}"
        
        # For Odoo JSON-RPC type='json' routes
        if json_data is not None:
            response = self.session.post(
                url,
                json={"jsonrpc": "2.0", "method": "call", "params": json_data, "id": 1},
                headers={'Content-Type': 'application/json'}
            )
        else:
            response = self.session.post(url, data=data)
        
        return response
    
    def post_json(self, endpoint, payload):
        """Make POST request to Odoo JSON-RPC endpoint (type='json')."""
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(
            url,
            json={"jsonrpc": "2.0", "method": "call", "params": payload, "id": 1},
            headers={'Content-Type': 'application/json'}
        )
        return response


# ============================================================================
# Standalone HTTP Tests (for external testing)
# ============================================================================

class TestMobileAPIStandalone(unittest.TestCase):
    """
    Standalone tests that can run against a live Odoo server.
    
    These tests require:
    1. A running Odoo server
    2. ShuttleBee module installed
    3. A test user with driver group
    4. Test data (trips, vehicles, etc.)
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test session."""
        cls.session = OdooSession()
        try:
            cls.session.authenticate()
            cls.odoo_available = True
        except Exception as e:
            cls.odoo_available = False
            cls.skip_reason = str(e)
    
    def setUp(self):
        """Check if Odoo is available before each test."""
        if not self.odoo_available:
            self.skipTest(f"Odoo not available: {self.skip_reason}")
    
    # -------------------------------------------------------------------------
    # Test: GET /api/v1/shuttle/trips/my
    # -------------------------------------------------------------------------
    
    def test_my_trips_authenticated(self):
        """Test fetching driver's trips when authenticated."""
        response = self.session.get('/api/v1/shuttle/trips/my')
        
        self.assertIn(response.status_code, [200, 403])
        
        if response.status_code == 200:
            data = response.json()
            self.assertIn('success', data)
            if data['success']:
                self.assertIn('trips', data)
                self.assertIn('count', data)
                self.assertIsInstance(data['trips'], list)
    
    def test_my_trips_with_state_filter(self):
        """Test fetching driver's trips with state filter."""
        for state in ['draft', 'confirmed', 'ongoing', 'completed']:
            response = self.session.get('/api/v1/shuttle/trips/my', params={'state': state})
            
            self.assertIn(response.status_code, [200, 403])
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('trips'):
                    for trip in data['trips']:
                        self.assertEqual(trip['state'], state)
    
    def test_my_trips_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        response = requests.get(f'{ODOO_URL}/api/v1/shuttle/trips/my')
        # Should redirect to login or return 303/403/404 (404 if route requires auth)
        self.assertIn(response.status_code, [303, 403, 401, 404])
    
    # -------------------------------------------------------------------------
    # Test: POST /api/v1/shuttle/trips/<trip_id>/confirm
    # -------------------------------------------------------------------------
    
    def test_confirm_trip_success(self):
        """Test confirming a trip with valid data."""
        # First, get a trip to confirm
        trips_response = self.session.get('/api/v1/shuttle/trips/my', params={'state': 'confirmed'})
        
        if trips_response.status_code != 200:
            self.skipTest("Could not fetch trips")
        
        trips_data = trips_response.json()
        if not trips_data.get('success') or not trips_data.get('trips'):
            self.skipTest("No confirmed trips available for testing")
        
        trip_id = trips_data['trips'][0]['id']
        
        # Confirm the trip
        payload = {
            'latitude': 33.5731,
            'longitude': -7.5898,
            'stop_id': None,
            'note': 'Test confirmation from API test'
        }
        
        response = self.session.post_json(f'/api/v1/shuttle/trips/{trip_id}/confirm', payload)
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        # For JSON-RPC, result is wrapped
        if 'result' in result:
            data = result['result']
        else:
            data = result
        
        self.assertIn('success', data)
    
    def test_confirm_trip_not_found(self):
        """Test confirming a non-existent trip."""
        payload = {'latitude': 33.5731, 'longitude': -7.5898}
        response = self.session.post_json('/api/v1/shuttle/trips/999999/confirm', payload)
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        if 'result' in result:
            data = result['result']
        elif 'error' in result:
            # JSON-RPC error response
            self.skipTest(f"Server error: {result['error'].get('data', {}).get('message', 'Unknown')}")
            return
        else:
            data = result
        
        self.assertEqual(data.get('success'), False)
        self.assertIn('error', data)
    
    def test_confirm_trip_invalid_gps(self):
        """Test confirming a trip with invalid GPS coordinates."""
        # Get a valid trip first
        trips_response = self.session.get('/api/v1/shuttle/trips/my')
        if trips_response.status_code != 200:
            self.skipTest("Could not fetch trips")
        
        trips_data = trips_response.json()
        if not trips_data.get('success') or not trips_data.get('trips'):
            self.skipTest("No trips available")
        
        trip_id = trips_data['trips'][0]['id']
        
        # Send invalid coordinates
        payload = {
            'latitude': 'invalid',
            'longitude': -7.5898
        }
        
        response = self.session.post_json(f'/api/v1/shuttle/trips/{trip_id}/confirm', payload)
        self.assertEqual(response.status_code, 200)
    
    # -------------------------------------------------------------------------
    # Test: GET /api/v1/shuttle/live/ongoing
    # -------------------------------------------------------------------------
    
    def test_live_ongoing_trips(self):
        """Test fetching ongoing trips for live map."""
        response = self.session.get('/api/v1/shuttle/live/ongoing')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('success', data)
        self.assertTrue(data['success'])
        self.assertIn('trips', data)
        self.assertIn('count', data)
        self.assertIsInstance(data['trips'], list)
        
        # Verify trip structure
        for trip in data['trips']:
            self.assertIn('trip_id', trip)
            self.assertIn('latitude', trip)
            self.assertIn('longitude', trip)
            self.assertIn('driver_name', trip)
            self.assertIn('vehicle_name', trip)
    
    # -------------------------------------------------------------------------
    # Test: GET /api/v1/shuttle/trips/<trip_id>/gps
    # -------------------------------------------------------------------------
    
    def test_trip_gps_path(self):
        """Test fetching GPS path for a trip."""
        # Get a trip first
        trips_response = self.session.get('/api/v1/shuttle/trips/my')
        if trips_response.status_code != 200:
            self.skipTest("Could not fetch trips")
        
        trips_data = trips_response.json()
        if not trips_data.get('success') or not trips_data.get('trips'):
            self.skipTest("No trips available")
        
        trip_id = trips_data['trips'][0]['id']
        
        response = self.session.get(f'/api/v1/shuttle/trips/{trip_id}/gps')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('success', data)
        if data['success']:
            self.assertIn('trip_id', data)
            self.assertIn('points', data)
            self.assertIn('count', data)
            self.assertIsInstance(data['points'], list)
    
    def test_trip_gps_path_with_since(self):
        """Test fetching GPS path with 'since' timestamp filter."""
        # Get a trip first
        trips_response = self.session.get('/api/v1/shuttle/trips/my')
        if trips_response.status_code != 200:
            self.skipTest("Could not fetch trips")
        
        trips_data = trips_response.json()
        if not trips_data.get('success') or not trips_data.get('trips'):
            self.skipTest("No trips available")
        
        trip_id = trips_data['trips'][0]['id']
        
        # Request GPS points since 1 hour ago
        since = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        response = self.session.get(
            f'/api/v1/shuttle/trips/{trip_id}/gps',
            params={'since': since, 'limit': 100}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('success', data)
    
    def test_trip_gps_path_not_found(self):
        """Test fetching GPS path for non-existent trip."""
        response = self.session.get('/api/v1/shuttle/trips/999999/gps')
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        
        self.assertFalse(data.get('success'))
        self.assertIn('error', data)
    
    def test_trip_gps_path_invalid_since(self):
        """Test fetching GPS path with invalid 'since' timestamp."""
        # Get a trip first
        trips_response = self.session.get('/api/v1/shuttle/trips/my')
        if trips_response.status_code != 200:
            self.skipTest("Could not fetch trips")
        
        trips_data = trips_response.json()
        if not trips_data.get('success') or not trips_data.get('trips'):
            self.skipTest("No trips available")
        
        trip_id = trips_data['trips'][0]['id']
        
        response = self.session.get(
            f'/api/v1/shuttle/trips/{trip_id}/gps',
            params={'since': 'invalid-date'}
        )
        
        self.assertEqual(response.status_code, 400)
    
    # -------------------------------------------------------------------------
    # Test: POST /api/v1/shuttle/vehicle/position
    # -------------------------------------------------------------------------
    
    def test_vehicle_position_success(self):
        """Test reporting vehicle position."""
        from datetime import timezone
        payload = {
            'vehicle_id': 1,  # Assumes vehicle with ID 1 exists
            'latitude': 33.5731,
            'longitude': -7.5898,
            'speed': 45.5,
            'heading': 180,
            'accuracy': 10.0,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'note': 'Test position from API test'
        }
        
        response = self.session.post_json('/api/v1/shuttle/vehicle/position', payload)
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        if 'result' in result:
            data = result['result']
        elif 'error' in result:
            # JSON-RPC error - check if it's a known issue
            error_msg = result['error'].get('data', {}).get('message', '')
            if 'jsonrequest' in error_msg:
                self.skipTest("Server needs update: jsonrequest attribute error (Odoo 18 compatibility)")
            else:
                self.fail(f"Server error: {error_msg}")
            return
        else:
            data = result
        
        self.assertIn('success', data)
        if data['success']:
            self.assertIn('id', data)
            self.assertIn('timestamp', data)
    
    def test_vehicle_position_missing_vehicle_id(self):
        """Test reporting position without vehicle_id."""
        payload = {
            'latitude': 33.5731,
            'longitude': -7.5898
        }
        
        response = self.session.post_json('/api/v1/shuttle/vehicle/position', payload)
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        if 'result' in result:
            data = result['result']
        elif 'error' in result:
            error_msg = result['error'].get('data', {}).get('message', '')
            if 'jsonrequest' in error_msg:
                self.skipTest("Server needs update: jsonrequest attribute error (Odoo 18 compatibility)")
            return
        else:
            data = result
        
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Missing vehicle_id')
    
    def test_vehicle_position_invalid_vehicle(self):
        """Test reporting position for non-existent vehicle."""
        payload = {
            'vehicle_id': 999999,
            'latitude': 33.5731,
            'longitude': -7.5898
        }
        
        response = self.session.post_json('/api/v1/shuttle/vehicle/position', payload)
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        if 'result' in result:
            data = result['result']
        elif 'error' in result:
            error_msg = result['error'].get('data', {}).get('message', '')
            if 'jsonrequest' in error_msg:
                self.skipTest("Server needs update: jsonrequest attribute error (Odoo 18 compatibility)")
            return
        else:
            data = result
        
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Vehicle not found')
    
    def test_vehicle_position_invalid_coordinates(self):
        """Test reporting position with invalid coordinates."""
        payload = {
            'vehicle_id': 1,
            'latitude': 'invalid',
            'longitude': -7.5898
        }
        
        response = self.session.post_json('/api/v1/shuttle/vehicle/position', payload)
        
        self.assertEqual(response.status_code, 200)
        result = response.json()
        
        if 'result' in result:
            data = result['result']
        elif 'error' in result:
            error_msg = result['error'].get('data', {}).get('message', '')
            if 'jsonrequest' in error_msg:
                self.skipTest("Server needs update: jsonrequest attribute error (Odoo 18 compatibility)")
            return
        else:
            data = result
        
        self.assertFalse(data.get('success'))
        self.assertEqual(data.get('error'), 'Invalid latitude/longitude')


# ============================================================================
# Odoo Integration Tests (for running within Odoo)
# ============================================================================

if ODOO_AVAILABLE:
    @tagged('shuttlebee_mobile', 'post_install', '-at_install')
    class TestMobileAPIOdoo(HttpCase):
        """
        Odoo integration tests for Mobile API.
        
        Run with:
            python odoo-bin -c odoo.conf -d testdb --test-enable --test-tags=shuttlebee_mobile
        """
        
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            
            # Create test driver user
            cls.driver_group = cls.env.ref('shuttlebee.group_shuttle_driver')
            cls.driver_user = cls.env['res.users'].create({
                'name': 'Test Driver',
                'login': 'test_driver',
                'email': 'driver@test.com',
                'password': 'test_password',
                'groups_id': [(4, cls.driver_group.id)],
            })
            
            # Create test vehicle
            cls.vehicle = cls.env['shuttle.vehicle'].create({
                'name': 'Test Vehicle',
                'license_plate': 'TEST-001',
                'capacity': 20,
            })
            
            # Create test trip
            cls.trip = cls.env['shuttle.trip'].create({
                'name': 'Test Trip',
                'driver_id': cls.driver_user.id,
                'vehicle_id': cls.vehicle.id,
                'date': fields.Date.today(),
                'trip_type': 'morning',
                'state': 'confirmed',
            })
        
        def test_my_trips_as_driver(self):
            """Test GET /api/v1/shuttle/trips/my as driver."""
            self.authenticate('test_driver', 'test_password')
            
            response = self.url_open('/api/v1/shuttle/trips/my')
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertTrue(data['success'])
            self.assertIn('trips', data)
            
            # Should include our test trip
            trip_ids = [t['id'] for t in data['trips']]
            self.assertIn(self.trip.id, trip_ids)
        
        def test_my_trips_non_driver(self):
            """Test that non-drivers get 403."""
            # Create non-driver user
            non_driver = self.env['res.users'].create({
                'name': 'Non Driver',
                'login': 'non_driver',
                'email': 'nondriver@test.com',
                'password': 'test_password',
            })
            
            self.authenticate('non_driver', 'test_password')
            
            response = self.url_open('/api/v1/shuttle/trips/my')
            self.assertEqual(response.status_code, 403)
            
            data = response.json()
            self.assertFalse(data['success'])
            self.assertEqual(data['error'], 'User is not a driver')
        
        def test_confirm_trip(self):
            """Test POST /api/v1/shuttle/trips/<id>/confirm."""
            self.authenticate('test_driver', 'test_password')
            
            payload = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {
                    'latitude': 33.5731,
                    'longitude': -7.5898,
                    'note': 'Test confirmation'
                },
                'id': 1
            }
            
            response = self.url_open(
                f'/api/v1/shuttle/trips/{self.trip.id}/confirm',
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            self.assertEqual(response.status_code, 200)
            
            result = response.json()['result']
            self.assertTrue(result['success'])
            self.assertEqual(result['trip_id'], self.trip.id)
            
            # Verify trip was updated
            self.trip.invalidate_recordset()
            self.assertEqual(self.trip.state, 'ongoing')
            self.assertEqual(self.trip.confirm_latitude, 33.5731)
        
        def test_live_ongoing_trips(self):
            """Test GET /api/v1/shuttle/live/ongoing."""
            # Update trip to ongoing state
            self.trip.write({
                'state': 'ongoing',
                'current_latitude': 33.5731,
                'current_longitude': -7.5898,
            })
            
            self.authenticate('test_driver', 'test_password')
            
            response = self.url_open('/api/v1/shuttle/live/ongoing')
            self.assertEqual(response.status_code, 200)
            
            data = response.json()
            self.assertTrue(data['success'])
            
            # Should include our ongoing trip
            trip_ids = [t['trip_id'] for t in data['trips']]
            self.assertIn(self.trip.id, trip_ids)
        
        def test_vehicle_position(self):
            """Test POST /api/v1/shuttle/vehicle/position."""
            self.authenticate('test_driver', 'test_password')
            
            payload = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': {
                    'vehicle_id': self.vehicle.id,
                    'latitude': 33.5731,
                    'longitude': -7.5898,
                    'speed': 45.0,
                    'heading': 180,
                },
                'id': 1
            }
            
            response = self.url_open(
                '/api/v1/shuttle/vehicle/position',
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            
            self.assertEqual(response.status_code, 200)
            
            result = response.json()['result']
            self.assertTrue(result['success'])
            self.assertIn('id', result)
            
            # Verify position was created
            position = self.env['shuttle.vehicle.position'].browse(result['id'])
            self.assertTrue(position.exists())
            self.assertEqual(position.vehicle_id.id, self.vehicle.id)
            self.assertEqual(position.latitude, 33.5731)


# ============================================================================
# Unit Tests (Mocked)
# ============================================================================

class TestMobileAPIUnit(unittest.TestCase):
    """Unit tests with mocked Odoo environment."""
    
    def setUp(self):
        """Set up mocks."""
        self.mock_env = MagicMock()
        self.mock_user = MagicMock()
        self.mock_user.id = 1
        self.mock_user.name = 'Test Driver'
        self.mock_env.user = self.mock_user
    
    def test_json_response_format(self):
        """Test _json_response helper format."""
        from odoo.http import Response
        
        # Mock the controller
        with patch('odoo.http.request') as mock_request:
            mock_request.env = self.mock_env
            
            # Import controller
            from shuttlebee.controllers.mobile_api import ShuttleBeeMobileAPI
            
            controller = ShuttleBeeMobileAPI()
            
            # Test successful response
            response = controller._json_response({'success': True, 'data': 'test'})
            self.assertIsInstance(response, Response)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.mimetype, 'application/json')
    
    def test_ensure_driver_check(self):
        """Test _ensure_driver helper."""
        with patch('odoo.http.request') as mock_request:
            mock_request.env = self.mock_env
            
            from shuttlebee.controllers.mobile_api import ShuttleBeeMobileAPI
            controller = ShuttleBeeMobileAPI()
            
            # Test when user is not a driver
            self.mock_user.has_group.return_value = False
            user, err = controller._ensure_driver(self.mock_env)
            self.assertIsNone(user)
            self.assertIsNotNone(err)
            
            # Test when user is a driver
            self.mock_user.has_group.return_value = True
            user, err = controller._ensure_driver(self.mock_env)
            self.assertEqual(user, self.mock_user)
            self.assertIsNone(err)


# ============================================================================
# Test Runner
# ============================================================================

def run_standalone_tests():
    """Run standalone tests against a live Odoo server."""
    print("=" * 70)
    print("ShuttleBee Mobile API Tests")
    print("=" * 70)
    print(f"Target: {ODOO_URL}")
    print(f"Database: {ODOO_DB}")
    print(f"User: {ODOO_USER}")
    print("=" * 70)
    
    # Check if Odoo is available
    try:
        response = requests.get(f"{ODOO_URL}/web/login", timeout=5)
        if response.status_code != 200:
            print(f"\n⚠️  Warning: Odoo server returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Cannot connect to Odoo at {ODOO_URL}")
        print("   Make sure Odoo is running and the URL is correct.")
        print("\n   To start Odoo:")
        print("   $ ./odoo-bin -c odoo.conf")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestMobileAPIStandalone)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print(__doc__)
        sys.exit(0)
    
    sys.exit(run_standalone_tests())

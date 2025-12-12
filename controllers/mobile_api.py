# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ShuttleBeeMobileAPI(http.Controller):
    """
    Minimal REST API for Flutter frontend.

    Authentication:
    - Odoo session (auth='user') using session cookie (recommended)
    """

    # -----------------------
    # Helpers
    # -----------------------
    def _json_response(self, data, status=200):
        return Response(json.dumps(data, ensure_ascii=False), status=status, mimetype='application/json')

    def _ensure_driver(self, env):
        if not env.user.has_group('shuttlebee.group_shuttle_driver'):
            return None, self._json_response({'success': False, 'error': 'User is not a driver'}, 403)
        return env.user, None

    # -----------------------
    # Endpoints
    # -----------------------
    @http.route('/api/v1/shuttle/trips/my', type='http', auth='user', methods=['GET'], csrf=False)
    def my_trips(self, **kwargs):
        env = request.env
        _, err = self._ensure_driver(env)
        if err:
            return err

        state = kwargs.get('state')
        domain = [('driver_id', '=', env.user.id)]
        if state:
            domain.append(('state', '=', state))
        trips = env['shuttle.trip'].search(domain, order='planned_start_time asc')

        data = []
        for t in trips:
            data.append({
                'id': t.id,
                'reference': t.reference,
                'name': t.name,
                'date': str(t.date) if t.date else None,
                'trip_type': t.trip_type,
                'state': t.state,
                'planned_start_time': t.planned_start_time.isoformat() if t.planned_start_time else None,
                'planned_arrival_time': t.planned_arrival_time.isoformat() if t.planned_arrival_time else None,
                'vehicle_id': t.vehicle_id.id if t.vehicle_id else None,
                'vehicle_name': t.vehicle_id.name if t.vehicle_id else None,
                'vehicle_plate': t.vehicle_id.license_plate if t.vehicle_id else None,
                'passenger_count': t.passenger_count,
                'current_latitude': t.current_latitude,
                'current_longitude': t.current_longitude,
                'last_gps_update': t.last_gps_update.isoformat() if t.last_gps_update else None,
                'confirm_latitude': t.confirm_latitude,
                'confirm_longitude': t.confirm_longitude,
                'confirm_stop_id': t.confirm_stop_id.id if t.confirm_stop_id else None,
                'confirm_stop_name': t.confirm_stop_id.name if t.confirm_stop_id else None,
                'confirm_note': t.confirm_note or '',
                'confirmed_at': t.confirmed_at.isoformat() if t.confirmed_at else None,
                'confirm_source': t.confirm_source or None,
            })

        return self._json_response({'success': True, 'count': len(data), 'trips': data})

    @http.route('/api/v1/shuttle/trips/<int:trip_id>/confirm', type='json', auth='user', methods=['POST'], csrf=False)
    def confirm_trip(self, trip_id, **kwargs):
        env = request.env
        _, err = self._ensure_driver(env)
        if err:
            # Convert Response into dict for JSON route
            return {'success': False, 'error': 'User is not a driver'}

        payload = request.jsonrequest or {}
        latitude = payload.get('latitude')
        longitude = payload.get('longitude')
        stop_id = payload.get('stop_id')
        note = payload.get('note') or payload.get('message')  # support both keys

        trip = env['shuttle.trip'].browse(trip_id)
        if not trip.exists():
            return {'success': False, 'error': 'Trip not found'}

        if trip.driver_id.id != env.user.id:
            return {'success': False, 'error': 'Not authorized'}

        # Normalize GPS
        if latitude is not None:
            latitude = float(latitude)
        if longitude is not None:
            longitude = float(longitude)

        trip._confirm_trip(source='driver_app', latitude=latitude, longitude=longitude, stop_id=stop_id, note=note)

        return {
            'success': True,
            'trip_id': trip.id,
            'new_state': trip.state,
            'confirmed_at': trip.confirmed_at.isoformat() if trip.confirmed_at else None,
            'confirm_stop_id': trip.confirm_stop_id.id if trip.confirm_stop_id else None,
            'confirm_stop_name': trip.confirm_stop_id.name if trip.confirm_stop_id else None,
        }

    @http.route('/api/v1/shuttle/live/ongoing', type='http', auth='user', methods=['GET'], csrf=False)
    def live_ongoing(self, **kwargs):
        """Return ongoing trips with latest coordinates (for live map)."""
        env = request.env

        # Dispatcher/Manager can see all; driver can see own; record rules enforce it.
        trips = env['shuttle.trip'].search([('state', '=', 'ongoing')], order='last_gps_update desc')
        items = []
        for t in trips:
            items.append({
                'trip_id': t.id,
                'reference': t.reference,
                'name': t.name,
                'trip_type': t.trip_type,
                'driver_id': t.driver_id.id if t.driver_id else None,
                'driver_name': t.driver_id.name if t.driver_id else None,
                'vehicle_id': t.vehicle_id.id if t.vehicle_id else None,
                'vehicle_name': t.vehicle_id.name if t.vehicle_id else None,
                'vehicle_plate': t.vehicle_id.license_plate if t.vehicle_id else None,
                'latitude': t.current_latitude,
                'longitude': t.current_longitude,
                'last_gps_update': t.last_gps_update.isoformat() if t.last_gps_update else None,
            })
        return self._json_response({'success': True, 'count': len(items), 'trips': items})

    @http.route('/api/v1/shuttle/trips/<int:trip_id>/gps', type='http', auth='user', methods=['GET'], csrf=False)
    def trip_gps_path(self, trip_id, **kwargs):
        """Return GPS points for a trip (optionally since a timestamp)."""
        env = request.env

        trip = env['shuttle.trip'].browse(trip_id)
        if not trip.exists():
            return self._json_response({'success': False, 'error': 'Trip not found'}, 404)

        since = kwargs.get('since')  # ISO string
        domain = [('trip_id', '=', trip.id)]
        if since:
            try:
                since_dt = env['ir.fields'].Datetime.to_datetime(since)
                domain.append(('timestamp', '>=', since_dt))
            except Exception:
                return self._json_response({'success': False, 'error': 'Invalid since timestamp'}, 400)

        limit = int(kwargs.get('limit', 500))
        points = env['shuttle.gps.position'].search(domain, order='timestamp asc', limit=limit)
        out = []
        for p in points:
            out.append({
                'id': p.id,
                'timestamp': p.timestamp.isoformat() if p.timestamp else None,
                'latitude': p.latitude,
                'longitude': p.longitude,
                'speed': p.speed,
                'heading': p.heading,
                'driver_id': p.driver_id.id if p.driver_id else None,
                'vehicle_id': p.vehicle_id.id if p.vehicle_id else None,
            })
        return self._json_response({'success': True, 'trip_id': trip.id, 'count': len(out), 'points': out})

    @http.route('/api/v1/shuttle/vehicle/position', type='json', auth='user', methods=['POST'], csrf=False)
    def vehicle_position(self, **kwargs):
        """
        Driver heartbeat endpoint (works even if all trips are draft).
        Body:
          { "vehicle_id": 1, "latitude": .., "longitude": .., "speed": .., "heading": .., "accuracy": .., "timestamp": .., "note": ".." }
        """
        env = request.env
        _, err = self._ensure_driver(env)
        if err:
            return {'success': False, 'error': 'User is not a driver'}

        data = request.jsonrequest or {}
        vehicle_id = data.get('vehicle_id')
        if not vehicle_id:
            return {'success': False, 'error': 'Missing vehicle_id'}

        vehicle = env['shuttle.vehicle'].browse(int(vehicle_id))
        if not vehicle.exists():
            return {'success': False, 'error': 'Vehicle not found'}

        # Normalize GPS
        try:
            latitude = float(data.get('latitude'))
            longitude = float(data.get('longitude'))
        except Exception:
            return {'success': False, 'error': 'Invalid latitude/longitude'}

        vals = {
            'vehicle_id': vehicle.id,
            'driver_id': env.user.id,
            'latitude': latitude,
            'longitude': longitude,
            'speed': data.get('speed'),
            'heading': data.get('heading'),
            'accuracy': data.get('accuracy'),
            'note': data.get('note') or data.get('message'),
        }
        if data.get('timestamp'):
            try:
                vals['timestamp'] = env['ir.fields'].Datetime.to_datetime(data['timestamp'])
            except Exception:
                pass

        pos = env['shuttle.vehicle.position'].create(vals)
        return {'success': True, 'id': pos.id, 'timestamp': pos.timestamp.isoformat() if pos.timestamp else None}



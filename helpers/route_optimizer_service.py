# -*- coding: utf-8 -*-
"""
Route Optimizer Service
=======================

Client for the Route Optimizer API that provides Vehicle Routing Problem (VRP) 
optimization for shuttle and delivery routes.

API Endpoint: POST /optimize
Modes: PASSENGERS, WEIGHT, VOLUME, COLIS, MULTI

Usage:
    from ..helpers.route_optimizer_service import RouteOptimizerService, RouteOptimizerError
    
    service = RouteOptimizerService(
        api_url='https://route-optimizer.geniura.com/optimize',
        timeout=60
    )
    
    result = service.optimize_passenger_route(
        depot={'id': 'depot', 'name': 'Bus Station', 'lat': 35.7796, 'lng': -5.8137},
        destination={'id': 'school', 'name': 'School', 'lat': 35.7650, 'lng': -5.8000},
        locations=[
            {'id': 'p1', 'name': 'Ahmed', 'lat': 35.7750, 'lng': -5.8200, 'passengers': 1},
        ],
        vehicles=[
            {'id': 'bus1', 'name': 'Bus 1', 'seats': 20},
        ]
    )
"""

import logging
import requests
from typing import List, Dict, Any, Optional, Literal

_logger = logging.getLogger(__name__)


class RouteOptimizerError(Exception):
    """Exception raised when route optimization fails"""
    
    def __init__(self, message: str, response_data: Optional[Dict] = None):
        self.message = message
        self.response_data = response_data
        super().__init__(self.message)


class RouteOptimizerService:
    """
    Client for the Route Optimizer API
    
    Supports:
    - PASSENGERS mode: Optimize by seat capacity (for shuttle/passenger transport)
    - WEIGHT mode: Optimize by weight in kg (for goods delivery)
    - VOLUME mode: Optimize by volume in m³
    - COLIS mode: Optimize by number of packages
    - MULTI mode: Optimize by multiple dimensions simultaneously
    """
    
    MODES = ('PASSENGERS', 'WEIGHT', 'VOLUME', 'COLIS', 'MULTI')
    
    def __init__(
        self,
        api_url: str = 'https://route-optimizer.geniura.com/optimize',
        timeout: int = 60,
        speed_kmh: float = 40.0,
        max_time_seconds: int = 30
    ):
        """
        Initialize the Route Optimizer Service
        
        Args:
            api_url: URL of the Route Optimizer API endpoint
            timeout: HTTP request timeout in seconds
            speed_kmh: Average vehicle speed for time estimation
            max_time_seconds: Maximum optimization time for the solver
        """
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        self.speed_kmh = speed_kmh
        self.max_time_seconds = max_time_seconds
    
    def _validate_location(self, location: Dict, name: str = 'location') -> None:
        """Validate a location dictionary has required fields"""
        required_fields = ['id', 'name', 'lat', 'lng']
        for field in required_fields:
            if field not in location:
                raise RouteOptimizerError(f"{name} missing required field: {field}")
        
        if not (-90 <= location['lat'] <= 90):
            raise RouteOptimizerError(f"{name} latitude must be between -90 and 90")
        if not (-180 <= location['lng'] <= 180):
            raise RouteOptimizerError(f"{name} longitude must be between -180 and 180")
    
    def _validate_vehicle(self, vehicle: Dict, mode: str) -> None:
        """Validate a vehicle dictionary has required fields for the mode"""
        if 'id' not in vehicle or 'name' not in vehicle:
            raise RouteOptimizerError("Vehicle missing required field: id or name")
        
        # Check capacity fields based on mode
        if mode == 'PASSENGERS' and vehicle.get('seats', 0) <= 0:
            raise RouteOptimizerError(f"Vehicle '{vehicle['name']}' must have positive seats for PASSENGERS mode")
        if mode == 'WEIGHT' and vehicle.get('max_weight', 0) <= 0:
            raise RouteOptimizerError(f"Vehicle '{vehicle['name']}' must have positive max_weight for WEIGHT mode")
        if mode == 'VOLUME' and vehicle.get('max_volume', 0) <= 0:
            raise RouteOptimizerError(f"Vehicle '{vehicle['name']}' must have positive max_volume for VOLUME mode")
        if mode == 'COLIS' and vehicle.get('max_colis', 0) <= 0:
            raise RouteOptimizerError(f"Vehicle '{vehicle['name']}' must have positive max_colis for COLIS mode")
    
    def optimize(
        self,
        mode: Literal['PASSENGERS', 'WEIGHT', 'VOLUME', 'COLIS', 'MULTI'],
        depot: Dict[str, Any],
        locations: List[Dict[str, Any]],
        vehicles: List[Dict[str, Any]],
        destination: Optional[Dict[str, Any]] = None,
        speed_kmh: Optional[float] = None,
        max_time_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Optimize routes using the Route Optimizer API
        
        Args:
            mode: Optimization mode (PASSENGERS, WEIGHT, VOLUME, COLIS, MULTI)
            depot: Starting point location
            locations: List of pickup/delivery locations
            vehicles: List of available vehicles
            destination: End point (if different from depot)
            speed_kmh: Override default average speed
            max_time_seconds: Override default max optimization time
        
        Returns:
            Dictionary with optimization results:
            {
                'success': bool,
                'message': str,
                'total_distance_km': float,
                'routes': [
                    {
                        'vehicle_id': str,
                        'vehicle_name': str,
                        'stops': [
                            {'order': int, 'location_id': str, 'location_name': str, 'lat': float, 'lng': float}
                        ],
                        'total_distance_km': float,
                        'total_time_minutes': int,
                        'passengers_count': int
                    }
                ],
                'unassigned': [str]  # List of unassigned location IDs
            }
        
        Raises:
            RouteOptimizerError: If optimization fails or API returns an error
        """
        # Validate mode
        if mode not in self.MODES:
            raise RouteOptimizerError(f"Invalid mode: {mode}. Must be one of {self.MODES}")
        
        # Validate depot
        self._validate_location(depot, 'Depot')
        
        # Validate destination if provided
        if destination:
            self._validate_location(destination, 'Destination')
        
        # Validate locations
        if not locations:
            raise RouteOptimizerError("At least one location is required")
        for i, loc in enumerate(locations):
            self._validate_location(loc, f'Location {i+1}')
        
        # Validate vehicles
        if not vehicles:
            raise RouteOptimizerError("At least one vehicle is required")
        for vehicle in vehicles:
            self._validate_vehicle(vehicle, mode)
        
        # Prepare request payload
        payload = {
            'mode': mode,
            'depot': depot,
            'destination': destination,
            'locations': locations,
            'vehicles': vehicles,
            'speed_kmh': speed_kmh or self.speed_kmh,
            'max_time_seconds': max_time_seconds or self.max_time_seconds
        }
        
        _logger.info(
            "Sending optimization request: mode=%s, locations=%d, vehicles=%d",
            mode, len(locations), len(vehicles)
        )
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            )
            
            # Check for HTTP errors
            if response.status_code != 200:
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', str(error_data))
                except Exception:
                    error_detail = response.text[:500]
                
                _logger.error(
                    "Route Optimizer API error: status=%d, detail=%s",
                    response.status_code, error_detail
                )
                raise RouteOptimizerError(
                    f"API error (HTTP {response.status_code}): {error_detail}",
                    response_data={'status_code': response.status_code, 'detail': error_detail}
                )
            
            result = response.json()
            
            _logger.info(
                "Optimization completed: success=%s, routes=%d, distance=%.2f km",
                result.get('success', False),
                len(result.get('routes', [])),
                result.get('total_distance_km', 0)
            )
            
            return result
            
        except requests.Timeout:
            _logger.error("Route Optimizer API timeout after %d seconds", self.timeout)
            raise RouteOptimizerError(f"API request timed out after {self.timeout} seconds")
        except requests.ConnectionError as e:
            _logger.error("Route Optimizer API connection error: %s", str(e))
            raise RouteOptimizerError(f"Failed to connect to Route Optimizer API: {str(e)}")
        except requests.RequestException as e:
            _logger.error("Route Optimizer API request error: %s", str(e))
            raise RouteOptimizerError(f"API request failed: {str(e)}")
    
    def optimize_passenger_route(
        self,
        depot: Dict[str, Any],
        locations: List[Dict[str, Any]],
        vehicles: List[Dict[str, Any]],
        destination: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimize passenger/shuttle routes (convenience method for PASSENGERS mode)
        
        Each location should have a 'passengers' field (number of passengers).
        Each vehicle should have a 'seats' field (seat capacity).
        
        Args:
            depot: Starting point (vehicle parking location)
            locations: List of passenger pickup locations with 'passengers' count
            vehicles: List of vehicles with 'seats' capacity
            destination: End point (e.g., school/office)
            **kwargs: Additional arguments passed to optimize()
        
        Returns:
            Optimization result dictionary
        """
        return self.optimize(
            mode='PASSENGERS',
            depot=depot,
            locations=locations,
            vehicles=vehicles,
            destination=destination,
            **kwargs
        )
    
    def optimize_goods_route(
        self,
        mode: Literal['WEIGHT', 'VOLUME', 'COLIS', 'MULTI'],
        depot: Dict[str, Any],
        locations: List[Dict[str, Any]],
        vehicles: List[Dict[str, Any]],
        destination: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Optimize goods delivery routes (convenience method for goods modes)
        
        For WEIGHT mode: locations need 'weight', vehicles need 'max_weight'
        For VOLUME mode: locations need 'volume', vehicles need 'max_volume'
        For COLIS mode: locations need 'colis', vehicles need 'max_colis'
        For MULTI mode: all above fields are considered
        
        Args:
            mode: One of WEIGHT, VOLUME, COLIS, MULTI
            depot: Starting point (warehouse location)
            locations: List of delivery locations with demand fields
            vehicles: List of vehicles with capacity fields
            destination: End point (if different from depot, e.g., for one-way deliveries)
            **kwargs: Additional arguments passed to optimize()
        
        Returns:
            Optimization result dictionary
        """
        if mode == 'PASSENGERS':
            raise RouteOptimizerError("Use optimize_passenger_route() for PASSENGERS mode")
        
        return self.optimize(
            mode=mode,
            depot=depot,
            locations=locations,
            vehicles=vehicles,
            destination=destination,
            **kwargs
        )
    
    def health_check(self) -> bool:
        """
        Check if the Route Optimizer API is healthy
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Get the base URL (remove /optimize)
            base_url = self.api_url.replace('/optimize', '')
            response = requests.get(
                f"{base_url}/health",
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('status') == 'healthy'
            return False
        except Exception as e:
            _logger.warning("Route Optimizer health check failed: %s", str(e))
            return False


def create_route_optimizer_service(env) -> RouteOptimizerService:
    """
    Factory function to create RouteOptimizerService from Odoo environment
    
    Reads configuration from ir.config_parameter:
    - shuttlebee.route_optimizer_url
    - shuttlebee.route_optimizer_timeout
    - shuttlebee.route_optimizer_speed_kmh
    - shuttlebee.route_optimizer_max_time
    
    Args:
        env: Odoo environment
    
    Returns:
        Configured RouteOptimizerService instance
    """
    IrConfigParam = env['ir.config_parameter'].sudo()
    
    api_url = IrConfigParam.get_param(
        'shuttlebee.route_optimizer_url',
        'https://route-optimizer.geniura.com/optimize'
    )
    timeout = int(IrConfigParam.get_param(
        'shuttlebee.route_optimizer_timeout', 60
    ) or 60)
    speed_kmh = float(IrConfigParam.get_param(
        'shuttlebee.route_optimizer_speed_kmh', 40.0
    ) or 40.0)
    max_time = int(IrConfigParam.get_param(
        'shuttlebee.route_optimizer_max_time', 30
    ) or 30)
    
    return RouteOptimizerService(
        api_url=api_url,
        timeout=timeout,
        speed_kmh=speed_kmh,
        max_time_seconds=max_time
    )


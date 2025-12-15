"""
Route optimization using KNN for smart waste collection.
This module calculates optimal routes based on bin fill predictions.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import math


class RouteOptimizer:
    """Optimizes collection routes using KNN-based nearest neighbor algorithm."""
    
    def __init__(self, depot_lat: float = 0.0, depot_lon: float = 0.0):
        """
        Initialize route optimizer.
        
        Args:
            depot_lat: Depot latitude (starting point)
            depot_lon: Depot longitude (starting point)
        """
        self.depot_lat = depot_lat
        self.depot_lon = depot_lon
        self.avg_speed_kmh = 30  # Average vehicle speed
    
    def haversine_distance(self, lat1: float, lon1: float, 
                          lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon / 2) ** 2)
        
        c = 2 * math.asin(math.sqrt(a))
        return R * c
    
    def find_nearest_neighbor(self, current: Tuple[float, float], 
                             candidates: List[Dict]) -> Tuple[int, Dict]:
        """
        Find nearest unvisited bin using KNN (K=1).
        
        Args:
            current: Current position (lat, lon)
            candidates: List of candidate bins with coordinates
            
        Returns:
            Tuple of (index, bin_dict)
        """
        min_dist = float('inf')
        nearest_idx = -1
        nearest_bin = None
        
        for idx, bin_data in enumerate(candidates):
            dist = self.haversine_distance(
                current[0], current[1],
                bin_data['lat'], bin_data['lon']
            )
            
            if dist < min_dist:
                min_dist = dist
                nearest_idx = idx
                nearest_bin = bin_data
        
        return nearest_idx, nearest_bin
    
    def optimize_route(self, bins: List[Dict], 
                      priority_threshold: float = 80.0) -> List[Dict]:
        """
        Create optimized route using nearest neighbor algorithm.
        
        Args:
            bins: List of bins with coordinates and fill levels
            priority_threshold: Minimum fill % to include in route
            
        Returns:
            List of route stops in optimal order
        """
        # Filter bins that need collection
        priority_bins = [
            b for b in bins 
            if b.get('predicted_fill_percent', 0) >= priority_threshold
        ]
        
        if not priority_bins:
            return []
        
        route = []
        unvisited = priority_bins.copy()
        current_pos = (self.depot_lat, self.depot_lon)
        
        # Start from depot
        route.append({
            'order_index': 0,
            'label': 'Depot (Start)',
            'bin_id': None,
            'lat': self.depot_lat,
            'lon': self.depot_lon,
            'distance_from_prev_km': 0.0,
            'est_travel_time_min': 0.0
        })
        
        # Visit bins using nearest neighbor
        while unvisited:
            nearest_idx, nearest_bin = self.find_nearest_neighbor(
                current_pos, unvisited
            )
            
            # Calculate distance and time
            distance = self.haversine_distance(
                current_pos[0], current_pos[1],
                nearest_bin['lat'], nearest_bin['lon']
            )
            travel_time = (distance / self.avg_speed_kmh) * 60  # minutes
            
            # Add stop to route
            route.append({
                'order_index': len(route),
                'label': f"Bin {nearest_bin['bin_id']}",
                'bin_id': nearest_bin['bin_id'],
                'lat': nearest_bin['lat'],
                'lon': nearest_bin['lon'],
                'distance_from_prev_km': round(distance, 2),
                'est_travel_time_min': round(travel_time, 1),
                'predicted_fill_percent': nearest_bin.get('predicted_fill_percent', 0)
            })
            
            # Update position and remove visited bin
            current_pos = (nearest_bin['lat'], nearest_bin['lon'])
            unvisited.pop(nearest_idx)
        
        # Return to depot
        distance = self.haversine_distance(
            current_pos[0], current_pos[1],
            self.depot_lat, self.depot_lon
        )
        travel_time = (distance / self.avg_speed_kmh) * 60
        
        route.append({
            'order_index': len(route),
            'label': 'Depot (End)',
            'bin_id': None,
            'lat': self.depot_lat,
            'lon': self.depot_lon,
            'distance_from_prev_km': round(distance, 2),
            'est_travel_time_min': round(travel_time, 1)
        })
        
        return route
    
    def calculate_route_stats(self, route: List[Dict]) -> Dict:
        """Calculate statistics for a route."""
        total_distance = sum(stop['distance_from_prev_km'] for stop in route)
        total_time = sum(stop['est_travel_time_min'] for stop in route)
        
        return {
            'total_stops': len(route) - 2,  # Exclude depot start/end
            'total_distance_km': round(total_distance, 2),
            'total_time_min': round(total_time, 1),
            'total_time_hours': round(total_time / 60, 2)
        }

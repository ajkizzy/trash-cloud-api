"""
Machine Learning predictor for waste bin fill levels.
Calculates predicted full time based on historical data and current fill level.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import func
from models import MLPrediction, Bin
from extensions import db


class WasteBinPredictor:
    """Predicts when a waste bin will be full based on fill rate."""
    
    def __init__(self):
        self.default_fill_rate = 1.5  # Default: 1.5% per hour
        self.min_data_points = 3  # Minimum readings needed for prediction
    
    def calculate_fill_rate(self, bin_id: str) -> Optional[float]:
        """
        Calculate fill rate (% per hour) from recent historical data.
        
        Args:
            bin_id: The trash bin identifier
            
        Returns:
            Fill rate in percentage per hour, or None if insufficient data
        """
        # Get bin object
        bin_obj = Bin.query.filter_by(trash_can_id=bin_id).first()
        if not bin_obj:
            return None
        
        # Get recent predictions (last 24 hours) ordered by time
        recent_predictions = (
            MLPrediction.query
            .filter(MLPrediction.bin_id == bin_obj.id)
            .filter(MLPrediction.source == "prototype")
            .filter(MLPrediction.created_at >= datetime.utcnow() - timedelta(hours=24))
            .order_by(MLPrediction.created_at.asc())
            .all()
        )
        
        # Need at least 2 data points to calculate rate
        if len(recent_predictions) < 2:
            return None
        
        # Calculate fill rate using linear regression on recent data
        fill_rates = []
        
        for i in range(1, len(recent_predictions)):
            prev = recent_predictions[i - 1]
            curr = recent_predictions[i]
            
            # Time difference in hours
            time_diff = (curr.created_at - prev.created_at).total_seconds() / 3600
            
            # Fill level difference
            fill_diff = curr.predicted_fill_percent - prev.predicted_fill_percent
            
            # Skip if time difference is too small (< 5 minutes)
            if time_diff < 0.083:  # 5 minutes
                continue
            
            # Calculate rate (% per hour)
            if time_diff > 0:
                rate = fill_diff / time_diff
                fill_rates.append(rate)
        
        if not fill_rates:
            return None
        
        # Return average fill rate
        avg_rate = sum(fill_rates) / len(fill_rates)
        
        # Ensure rate is positive (bins shouldn't empty themselves)
        return max(0.1, avg_rate)  # Minimum 0.1% per hour
    
    def predict_full_time(
        self, 
        bin_id: str, 
        current_fill_percent: float
    ) -> Optional[datetime]:
        """
        Predict when bin will be full (100%).
        
        Args:
            bin_id: The trash bin identifier
            current_fill_percent: Current fill level (0-100)
            
        Returns:
            Datetime when bin is predicted to be full, or None if can't predict
        """
        # If already full or nearly full, predict very soon
        if current_fill_percent >= 95:
            return datetime.utcnow() + timedelta(hours=1)
        
        # Try to calculate fill rate from history
        fill_rate = self.calculate_fill_rate(bin_id)
        
        # If no historical data, use default rate
        if fill_rate is None or fill_rate <= 0:
            fill_rate = self.default_fill_rate
        
        # Calculate hours until full
        remaining_capacity = 100 - current_fill_percent
        hours_until_full = remaining_capacity / fill_rate
        
        # Cap at reasonable maximum (30 days)
        hours_until_full = min(hours_until_full, 24 * 30)
        
        # Calculate predicted time
        predicted_time = datetime.utcnow() + timedelta(hours=hours_until_full)
        
        return predicted_time
    
    def predict_with_confidence(
        self, 
        bin_id: str, 
        current_fill_percent: float
    ) -> Tuple[Optional[datetime], str]:
        """
        Predict full time with confidence level.
        
        Args:
            bin_id: The trash bin identifier
            current_fill_percent: Current fill level (0-100)
            
        Returns:
            Tuple of (predicted_time, confidence_level)
            confidence_level: "high", "medium", "low"
        """
        bin_obj = Bin.query.filter_by(trash_can_id=bin_id).first()
        if not bin_obj:
            return None, "low"
        
        # Count recent data points
        data_count = (
            MLPrediction.query
            .filter(MLPrediction.bin_id == bin_obj.id)
            .filter(MLPrediction.source == "prototype")
            .filter(MLPrediction.created_at >= datetime.utcnow() - timedelta(hours=24))
            .count()
        )
        
        predicted_time = self.predict_full_time(bin_id, current_fill_percent)
        
        # Determine confidence based on available data
        if data_count >= 10:
            confidence = "high"
        elif data_count >= 5:
            confidence = "medium"
        else:
            confidence = "low"
        
        return predicted_time, confidence
    
    def get_bin_statistics(self, bin_id: str) -> dict:
        """
        Get statistical information about a bin's fill patterns.
        
        Args:
            bin_id: The trash bin identifier
            
        Returns:
            Dictionary with statistics
        """
        bin_obj = Bin.query.filter_by(trash_can_id=bin_id).first()
        if not bin_obj:
            return {}
        
        # Get predictions from last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        predictions = (
            MLPrediction.query
            .filter(MLPrediction.bin_id == bin_obj.id)
            .filter(MLPrediction.source == "prototype")
            .filter(MLPrediction.created_at >= week_ago)
            .all()
        )
        
        if not predictions:
            return {"data_points": 0}
        
        fill_levels = [p.predicted_fill_percent for p in predictions]
        
        return {
            "data_points": len(predictions),
            "current_fill": fill_levels[-1] if fill_levels else 0,
            "avg_fill": sum(fill_levels) / len(fill_levels),
            "max_fill": max(fill_levels),
            "min_fill": min(fill_levels),
            "fill_rate": self.calculate_fill_rate(bin_id)
        }


# Global predictor instance
predictor = WasteBinPredictor()

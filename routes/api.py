from flask import Blueprint, request, jsonify
from datetime import datetime
from models import Bin, MLPrediction, Route, RouteStop
from extensions import db

api_bp = Blueprint("api", __name__)

@@ -90,3 +92,109 @@ def api_route():
            "stops": stop_list,
        }
    )


# ---------- Raspberry Pi Prototype Data Submission ----------

@api_bp.route("/api/prototype/submit", methods=["POST"])
def submit_prototype_data():
    """
    Receive prototype bin data from Raspberry Pi.
    
    Expected JSON:
    {
        "bin_id": "BIN_RPI_001",
        "fill_percent": 75.5,
        "latitude": 55.6761,
        "longitude": 12.5683,
        "location_name": "Test Location",
        "capacity_litres": 120,
        "predicted_full_at": "2025-12-20 14:30:00"  (optional)
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Required fields
        bin_id = data.get("bin_id")
        fill_percent = data.get("fill_percent")
        
        if not bin_id or fill_percent is None:
            return jsonify({"error": "bin_id and fill_percent are required"}), 400
        
        # Optional fields
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        location_name = data.get("location_name", "Prototype Location")
        capacity_litres = data.get("capacity_litres", 120)
        predicted_full_str = data.get("predicted_full_at")
        
        # Parse predicted_full_at if provided
        predicted_full_at = None
        if predicted_full_str:
            try:
                predicted_full_at = datetime.fromisoformat(predicted_full_str)
            except ValueError:
                try:
                    predicted_full_at = datetime.strptime(predicted_full_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass  # Leave as None if can't parse
        
        # Get or create Bin
        bin_obj = Bin.query.filter_by(trash_can_id=bin_id).first()
        
        if not bin_obj:
            bin_obj = Bin(
                trash_can_id=bin_id,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                capacity_litres=capacity_litres,
                is_active=True
            )
            db.session.add(bin_obj)
            db.session.flush()
        else:
            # Update location if provided
            if latitude is not None:
                bin_obj.latitude = latitude
            if longitude is not None:
                bin_obj.longitude = longitude
            if location_name:
                bin_obj.location_name = location_name
        
        # Create ML Prediction
        prediction = MLPrediction(
            bin=bin_obj,
            source="prototype",
            predicted_fill_percent=float(fill_percent),
            predicted_full_at=predicted_full_at
        )
        db.session.add(prediction)
        db.session.commit()
        
        return jsonify({
            "success": True,
            "message": f"Data received for bin {bin_id}",
            "bin_id": bin_id,
            "fill_percent": fill_percent,
            "timestamp": datetime.utcnow().isoformat()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ---------- Health Check ----------

@api_bp.route("/api/health")
def health_check():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    })

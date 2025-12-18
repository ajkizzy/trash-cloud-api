from flask import Blueprint, request, jsonify
from datetime import datetime
from models import Bin, MLPrediction, Route, RouteStop
from extensions import db

api_bp = Blueprint("api", __name__)


# ---------- Predictions API ----------

@api_bp.route("/api/predictions")
def api_predictions():
    """
    Return a list of predictions (test or prototype).

    - test: ordered by predicted full time then fill%
    - prototype: ordered by recorded time (latest first)
    """
    source = request.args.get("source", "test")  # "test" or "prototype"

    # =========================
    # PROTOTYPE (LIVE SENSOR DATA)
    # =========================
    if source == "prototype":
        query = (
            MLPrediction.query.join(Bin)
            .filter(MLPrediction.source == "prototype")
            .order_by(MLPrediction.created_at.desc())  # ✅ newest first
        )

        results = []
        for p in query.all():
            bin_obj = p.bin

            results.append(
                {
                    "bin_id": bin_obj.trash_can_id if bin_obj else None,
                    "location_name": bin_obj.location_name if bin_obj else None,
                    "lat": bin_obj.latitude if bin_obj else None,
                    "lon": bin_obj.longitude if bin_obj else None,
                    "predicted_fill_percent": p.predicted_fill_percent,
                    "predicted_full_at": (
                        p.predicted_full_at.isoformat()
                        if p.predicted_full_at else None
                    ),
                    # ✅ NEW FIELD FOR TAB 3
                    "recorded_at": p.created_at.isoformat(),
                }
            )

        return jsonify(results)

    # =========================
    # TEST DATA (UNCHANGED LOGIC)
    # =========================
    query = (
        MLPrediction.query.join(Bin)
        .filter(MLPrediction.source == "test")
        .order_by(
            MLPrediction.predicted_full_at,
            MLPrediction.predicted_fill_percent.desc(),
        )
    )

    results = []
    for p in query.all():
        bin_obj = p.bin

        results.append(
            {
                "bin_id": bin_obj.trash_can_id if bin_obj else None,
                "location_name": bin_obj.location_name if bin_obj else None,
                "lat": bin_obj.latitude if bin_obj else None,
                "lon": bin_obj.longitude if bin_obj else None,
                "predicted_fill_percent": p.predicted_fill_percent,
                "predicted_full_at": (
                    p.predicted_full_at.isoformat()
                    if p.predicted_full_at else None
                ),
            }
        )

    return jsonify(results)


# ---------- Route API ----------

@api_bp.route("/api/route")
def api_route():
    """
    Return the latest route for a given source ("test" or "prototype").
    """
    source = request.args.get("source", "test")

    route = (
        Route.query.filter_by(source=source)
        .order_by(Route.created_at.desc())
        .first()
    )
    if not route:
        return jsonify({"route_id": None, "name": None, "source": source, "stops": []})

    stops = (
        RouteStop.query.filter_by(route_id=route.id)
        .order_by(RouteStop.order_index)
        .all()
    )

    stop_list = []
    for s in stops:
        bin_obj = s.bin
        stop_list.append(
            {
                "order_index": s.order_index,
                "label": s.label,
                "bin_id": bin_obj.trash_can_id if bin_obj else None,
                "lat": s.latitude,
                "lon": s.longitude,
                "distance_from_prev_km": s.distance_from_prev_km,
                "est_travel_time_min": s.est_travel_time_min,
            }
        )

    return jsonify(
        {
            "route_id": route.id,
            "name": route.name,
            "source": route.source,
            "stops": stop_list,
        }
    )


# ---------- Raspberry Pi Prototype Data Submission ----------

@api_bp.route("/api/prototype/submit", methods=["POST"])
def submit_prototype_data():
    """
    Receive prototype bin data from Raspberry Pi.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        bin_id = data.get("bin_id")
        fill_percent = data.get("fill_percent")

        if not bin_id or fill_percent is None:
            return jsonify({"error": "bin_id and fill_percent are required"}), 400

        latitude = data.get("latitude")
        longitude = data.get("longitude")
        location_name = data.get("location_name", "Prototype Location")
        capacity_litres = data.get("capacity_litres", 120)
        predicted_full_str = data.get("predicted_full_at")

        predicted_full_at = None
        if predicted_full_str:
            try:
                predicted_full_at = datetime.fromisoformat(predicted_full_str)
            except ValueError:
                try:
                    predicted_full_at = datetime.strptime(
                        predicted_full_str, "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    pass

        bin_obj = Bin.query.filter_by(trash_can_id=bin_id).first()

        if not bin_obj:
            bin_obj = Bin(
                trash_can_id=bin_id,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                capacity_litres=capacity_litres,
                is_active=True,
            )
            db.session.add(bin_obj)
            db.session.flush()
        else:
            if latitude is not None:
                bin_obj.latitude = latitude
            if longitude is not None:
                bin_obj.longitude = longitude
            if location_name:
                bin_obj.location_name = location_name

        prediction = MLPrediction(
            bin=bin_obj,
            source="prototype",
            predicted_fill_percent=float(fill_percent),
            predicted_full_at=predicted_full_at,
        )

        db.session.add(prediction)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": f"Data received for bin {bin_id}",
                "bin_id": bin_id,
                "fill_percent": fill_percent,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ---------- Health Check ----------

@api_bp.route("/api/health")
def health_check():
    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

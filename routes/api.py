from flask import Blueprint, request, jsonify
from models import Bin, MLPrediction, Route, RouteStop

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/predictions")
def api_predictions():
    source = request.args.get("source", "test")  # "test" or "prototype"

    query = (
        MLPrediction.query.join(Bin)
        .filter(MLPrediction.source == source)
        .order_by(
            MLPrediction.predicted_full_at,
            MLPrediction.predicted_fill_percent.desc(),
        )
    )

    results = []
    for p in query.all():
        results.append(
            {
                "bin_id": p.bin.trash_can_id,
                "location_name": p.bin.location_name,
                "lat": p.bin.latitude,
                "lon": p.bin.longitude,
                "predicted_fill_percent": p.predicted_fill_percent,
                "predicted_full_at": p.predicted_full_at.isoformat()
                if p.predicted_full_at
                else None,
            }
        )

    return jsonify(results)


@api_bp.route("/api/route")
def api_route():
    source = request.args.get("source", "test")

    route = (
        Route.query.filter_by(source=source)
        .order_by(Route.created_at.desc())
        .first()
    )
    if not route:
        return jsonify({"route_id": None, "name": None, "stops": []})

    stops = (
        RouteStop.query.filter_by(route_id=route.id)
        .order_by(RouteStop.order_index)
        .all()
    )

    stop_list = []
    for s in stops:
        stop_list.append(
            {
                "order_index": s.order_index,
                "label": s.label,
                "bin_id": s.bin.trash_can_id if s.bin else None,
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

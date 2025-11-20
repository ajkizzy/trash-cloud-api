from flask import Blueprint, request, jsonify
from models import Bin, MLPrediction, Route, RouteStop

api_bp = Blueprint("api", __name__)


# ---------- Predictions API ----------

@api_bp.route("/api/predictions")
def api_predictions():
    """
    Return a list of predictions (test or prototype) ordered by
    predicted full time then fill% desc.

    JSON shape (per row):
    {
      "bin_id": "...",
      "location_name": "...",
      "lat": 57.048,
      "lon": 9.921,
      "predicted_fill_percent": 73.0,
      "predicted_full_at": "2023-04-03T10:31:19.644012"
    }
    """
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
        bin_obj = p.bin

        results.append(
            {
                "bin_id": bin_obj.trash_can_id if bin_obj else None,
                "location_name": bin_obj.location_name if bin_obj else None,
                # expose as 'lat' / 'lon' for the frontend, but read from your model fields
                "lat": getattr(bin_obj, "latitude", None),
                "lon": getattr(bin_obj, "longitude", None),
                "predicted_fill_percent": p.predicted_fill_percent,
                "predicted_full_at": (
                    p.predicted_full_at.isoformat() if p.predicted_full_at else None
                ),
            }
        )

    return jsonify(results)


# ---------- Route API ----------

@api_bp.route("/api/route")
def api_route():
    """
    Return the latest route for a given source ("test" or "prototype").

    JSON shape:
    {
      "route_id": 1,
      "name": "Morning Test Route",
      "source": "test",
      "stops": [
        {
          "order_index": 1,
          "label": "Bin 6092",
          "bin_id": "6092",
          "lat": 57.048,
          "lon": 9.921,
          "distance_from_prev_km": 1.23,
          "est_travel_time_min": 4.5
        },
        ...
      ]
    }
    """
    source = request.args.get("source", "test")

    # Latest route for this source
    route = (
        Route.query.filter_by(source=source)
        .order_by(Route.created_at.desc())
        .first()
    )
    if not route:
        return jsonify({"route_id": None, "name": None, "source": source, "stops": []})

    # Stops ordered by the index you store in the DB
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
                # again, expose as 'lat' / 'lon' for the frontend
                "lat": getattr(s, "latitude", None),
                "lon": getattr(s, "longitude", None),
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

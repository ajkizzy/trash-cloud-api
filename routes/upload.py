from flask import Blueprint, render_template, request
from datetime import datetime
import csv
import io

from extensions import db
from models import Bin, MLPrediction, Route, RouteStop

upload_bp = Blueprint("upload", __name__, url_prefix="/dev")


# ---------- Upload TEST PREDICTIONS CSV ----------

@upload_bp.route("/upload_test_predictions", methods=["GET", "POST"])
def upload_test_predictions():
    message = None
    error = None

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            error = "Please choose a CSV file to upload."
        else:
            try:
                text_stream = io.TextIOWrapper(
                    file.stream, encoding="utf-8", newline=""
                )
                reader = csv.DictReader(text_stream)

                max_rows = 5000  # safety limit for Render free tier
                created_bins = 0
                created_preds = 0

                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break

                    bin_code = (row.get("bin_id") or "").strip()
                    if not bin_code:
                        continue

                    # --- parse coordinates from CSV (columns: lat, lon) ---
                    lat_raw = row.get("lat")
                    lon_raw = row.get("lon")
                    loc_name = row.get("location_name") or None

                    try:
                        lat = float(lat_raw) if lat_raw not in (None, "", "NaN") else None
                    except ValueError:
                        lat = None

                    try:
                        lon = float(lon_raw) if lon_raw not in (None, "", "NaN") else None
                    except ValueError:
                        lon = None

                    # --- upsert Bin with correct model fields (latitude/longitude) ---
                    bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()

                    if not bin_obj:
                        bin_obj = Bin(
                            trash_can_id=bin_code,
                            latitude=lat,
                            longitude=lon,
                            location_name=loc_name or "Unknown",
                        )
                        db.session.add(bin_obj)
                        created_bins += 1
                    else:
                        if lat is not None:
                            bin_obj.latitude = lat
                        if lon is not None:
                            bin_obj.longitude = lon
                        if loc_name:
                            bin_obj.location_name = loc_name

                    # --- prediction values ---
                    try:
                        fill_pct = float(row.get("current_fill_pct") or 0)
                    except ValueError:
                        fill_pct = 0.0

                    pf_str = (row.get("predicted_full_at") or "").strip()
                    pf_at = None
                    if pf_str:
                        try:
                            pf_at = datetime.fromisoformat(pf_str)
                        except ValueError:
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                                try:
                                    pf_at = datetime.strptime(pf_str, fmt)
                                    break
                                except ValueError:
                                    continue

                    pred = MLPrediction(
                        bin=bin_obj,
                        source="test",
                        predicted_fill_percent=fill_pct,
                        predicted_full_at=pf_at,
                    )
                    db.session.add(pred)
                    created_preds += 1

                db.session.commit()
                message = (
                    f"Uploaded {created_bins} bins and {created_preds} "
                    f"test predictions (first {max_rows} rows)."
                )

            except Exception as e:
                db.session.rollback()
                error = f"Error while processing file: {e}"

    return render_template(
        "upload_test_predictions.html",
        message=message,
        error=error,
    )


# ---------- Upload OPTIMAL ROUTE CSV (TEST DATASET) ----------

@upload_bp.route("/upload_route_test", methods=["GET", "POST"])
def upload_route_test():
    message = None
    error = None

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            error = "Please choose a CSV file to upload."
        else:
            try:
                text_stream = io.TextIOWrapper(
                    file.stream, encoding="utf-8", newline=""
                )
                reader = csv.DictReader(text_stream)

                # Expected columns:
                # route_name, order_index, bin_id, lat, lon,
                # distance_from_prev_km, est_travel_time_min

                # Clear existing test routes + stops (keep only one for demo)
                existing_routes = Route.query.filter_by(source="test").all()
                for r in existing_routes:
                    RouteStop.query.filter_by(route_id=r.id).delete()
                    db.session.delete(r)
                db.session.commit()

                created_route = None
                created_stops = 0

                for i, row in enumerate(reader):
                    route_name = row.get("route_name") or "Test Route"
                    order_raw = row.get("order_index") or row.get("stop_order") or (i + 1)
                    bin_code = (row.get("bin_id") or "").strip()

                    try:
                        order_index = int(order_raw)
                    except ValueError:
                        order_index = i + 1

                    try:
                        lat = float(row.get("lat") or 0)
                    except ValueError:
                        lat = 0.0

                    try:
                        lon = float(row.get("lon") or 0)
                    except ValueError:
                        lon = 0.0

                    try:
                        dist_km = float(row.get("distance_from_prev_km") or 0)
                    except ValueError:
                        dist_km = 0.0

                    try:
                        travel_min = float(row.get("est_travel_time_min") or 0)
                    except ValueError:
                        travel_min = 0.0

                    if created_route is None:
                        created_route = Route(
                            name=route_name,
                            source="test",
                        )
                        db.session.add(created_route)
                        db.session.flush()  # populate id

                    bin_obj = None
                    if bin_code:
                        bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()

                    stop = RouteStop(
                        route_id=created_route.id,
                        order_index=order_index,
                        label=f"Bin {bin_code}" if bin_code else f"Stop {order_index}",
                        bin=bin_obj,
                        latitude=lat,
                        longitude=lon,
                        distance_from_prev_km=dist_km,
                        est_travel_time_min=travel_min,
                    )
                    db.session.add(stop)
                    created_stops += 1

                db.session.commit()

                if created_route:
                    message = (
                        f"Uploaded route '{created_route.name}' with "
                        f"{created_stops} stops (test dataset)."
                    )
                else:
                    error = "No route rows found in CSV."

            except Exception as e:
                db.session.rollback()
                error = f"Error while processing route CSV: {e}"

    return render_template(
        "upload_route_test.html",
        message=message,
        error=error,
    )

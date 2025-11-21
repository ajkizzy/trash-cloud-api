from flask import Blueprint, render_template, request
from extensions import db
from models import Bin, Route, RouteStop
import csv
import io

# This blueprint is mounted with url_prefix="/dev" in app.py
upload_route_bp = Blueprint("upload_route", __name__, url_prefix="/dev")


@upload_route_bp.route("/upload_route_test", methods=["GET", "POST"])
def upload_route_test():
    """
    Upload a CSV containing an optimal route for the TEST dataset.

    Expected columns in the CSV:
      - route_name
      - order_index
      - bin_id
      - lat
      - lon
      - distance_from_prev_km
      - est_travel_time_min
    """
    message = None
    error = None

    if request.method == "POST":
        # Support both 'file' and 'csv_file' as input names
        file = request.files.get("file") or request.files.get("csv_file")

        if not file or file.filename == "":
            error = "Please choose a CSV file to upload."
        else:
            try:
                # Wrap the raw file in a text stream
                text_stream = io.TextIOWrapper(file.stream, encoding="utf-8", newline="")
                reader = csv.DictReader(text_stream)

                required_cols = [
                    "route_name",
                    "order_index",
                    "bin_id",
                    "lat",
                    "lon",
                    "distance_from_prev_km",
                    "est_travel_time_min",
                ]
                for col in required_cols:
                    if col not in reader.fieldnames:
                        raise ValueError(f"Missing required column: {col}")

                # Create a new Route (source="test"), we will attach stops to it
                route_obj = None
                stop_count = 0

                for row in reader:
                    # lazily create Route once we see first row
                    if route_obj is None:
                        route_name = row.get("route_name") or "Test Route"
                        route_obj = Route(
                            name=route_name,
                            source="test",
                        )
                        db.session.add(route_obj)
                        db.session.flush()  # populate route_obj.id

                    # Parse fields from CSV
                    bin_code = (row.get("bin_id") or "").strip()
                    try:
                        order_index = int(row.get("order_index") or 0)
                    except ValueError:
                        order_index = stop_count + 1

                    # Coordinates
                    try:
                        lat = float(row.get("lat") or 0)
                    except ValueError:
                        lat = 0.0

                    try:
                        lon = float(row.get("lon") or 0)
                    except ValueError:
                        lon = 0.0

                    # Distance + time
                    try:
                        dist_km = float(row.get("distance_from_prev_km") or 0)
                    except ValueError:
                        dist_km = 0.0

                    try:
                        travel_min = float(row.get("est_travel_time_min") or 0)
                    except ValueError:
                        travel_min = 0.0

                    # Try to look up the Bin by trash_can_id if present
                    bin_obj = None
                    if bin_code:
                        bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()

                    # Create RouteStop
                    stop = RouteStop(
                        route_id=route_obj.id,
                        order_index=order_index,
                        label=f"Bin {bin_code}" if bin_code else f"Stop {order_index}",
                        bin=bin_obj,
                        latitude=lat,
                        longitude=lon,
                        distance_from_prev_km=dist_km,
                        est_travel_time_min=travel_min,
                    )
                    db.session.add(stop)
                    stop_count += 1

                if route_obj is None:
                    error = "No valid rows found in CSV."
                    db.session.rollback()
                else:
                    db.session.commit()
                    message = f"Uploaded route '{route_obj.name}' with {stop_count} stops (test dataset)."

            except Exception as e:
                db.session.rollback()
                error = f"Error while processing route CSV: {e}"

    # Render a simple upload page
    return render_template(
        "upload_route_test.html",
        message=message,
        error=error,
    )

from flask import Blueprint, render_template, request, redirect, flash
from models import db, Route, RouteStop

upload_route_bp = Blueprint("upload_route", __name__)

@upload_route_bp.route("/dev/upload_route_test", methods=["GET", "POST"])
def upload_route_test():
    if request.method == "GET":
        return render_template("upload_route_test.html")

    file = request.files.get("csv_file")
    if not file:
        flash("No file selected.", "danger")
        return redirect(request.url)

    import pandas as pd
    df = pd.read_csv(file)

    # Validate required columns
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
        if col not in df.columns:
            flash(f"Missing column: {col}", "danger")
            return redirect(request.url)

    # Create Route record
    route = Route(name=df["route_name"][0], source="test")
    db.session.add(route)
    db.session.commit()

    # Insert stops
    for _, row in df.iterrows():
        stop = RouteStop(
            route_id=route.id,
            order_index=int(row["order_index"]),
            bin_id=str(row["bin_id"]),
            latitude=float(row["lat"]),
            longitude=float(row["lon"]),
            distance_from_prev_km=float(row["distance_from_prev_km"]),
            est_travel_time_min=float(row["est_travel_time_min"]),
            label=f"Bin {row['bin_id']}",
        )
        db.session.add(stop)

    db.session.commit()

    flash(f"Uploaded route '{route.name}' with {len(df)} stops.", "success")
    return redirect("/dashboard")

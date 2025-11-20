from flask import Blueprint, render_template, request
from datetime import datetime
import csv
import io

from extensions import db
from models import Bin, MLPrediction

upload_bp = Blueprint("upload", __name__, url_prefix="/dev")


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

                    # --- Upsert Bin with location info ---
                    bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()

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

                    if not bin_obj:
                        bin_obj = Bin(
                            trash_can_id=bin_code,
                            lat=lat,
                            lon=lon,
                            location_name=loc_name or "Unknown",
                        )
                        db.session.add(bin_obj)
                        created_bins += 1
                    else:
                        # update existing bin’s location info if we have values
                        if lat is not None:
                            bin_obj.lat = lat
                        if lon is not None:
                            bin_obj.lon = lon
                        if loc_name:
                            bin_obj.location_name = loc_name

                    # --- Prediction values ---
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
                            try:
                                pf_at = datetime.strptime(pf_str, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                pf_at = None

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

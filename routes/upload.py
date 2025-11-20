from flask import Blueprint, render_template, request
from datetime import datetime, timedelta
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
                # Wrap uploaded file as text
                text_stream = io.TextIOWrapper(
                    file.stream, encoding="utf-8", newline=""
                )
                reader = csv.DictReader(text_stream)

                if not reader.fieldnames:
                    error = "CSV appears to have no header row."
                else:
                    fields = [c.strip() for c in reader.fieldnames]
                    print("🔎 CSV columns:", fields)

                    # Try to guess column names
                    def pick(*candidates):
                        for c in candidates:
                            if c in fields:
                                return c
                        return None

                    bin_col = pick("bin_id", "BinID", "ContainerID", "container_id")
                    fill_col = pick(
                        "current_fill_pct",
                        "fill_pct",
                        "fill_percent",
                        "fill_percentage",
                    )
                    pred_full_col = pick(
                        "predicted_full_at", "predicted_full_time", "full_at"
                    )
                    pred_ts_col = pick("prediction_ts", "ts", "timestamp")
                    pred_hrs_col = pick(
                        "predicted_hrs_to_90",
                        "hrs_to_90",
                        "hours_to_90",
                        "hours_to_full",
                    )

                    if not bin_col:
                        raise ValueError(
                            "Could not find a bin ID column. "
                            "Expected one of: bin_id, BinID, ContainerID, container_id."
                        )

                    if not fill_col:
                        raise ValueError(
                            "Could not find a fill percentage column. "
                            "Expected one of: current_fill_pct, fill_pct, fill_percent."
                        )

                    created_bins = 0
                    created_preds = 0

                    for row in reader:
                        bin_code = (row.get(bin_col) or "").strip()
                        if not bin_code:
                            continue

                        # Find or create bin
                        bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()
                        if not bin_obj:
                            bin_obj = Bin(trash_can_id=bin_code)
                            db.session.add(bin_obj)
                            created_bins += 1

                        # Fill %
                        try:
                            fill_pct = float(row.get(fill_col) or 0)
                        except ValueError:
                            fill_pct = 0.0

                        # Predicted full timestamp: several fallbacks
                        pf_at = None

                        # 1) Direct predicted_full_at column
                        if pred_full_col:
                            pf_str = (row.get(pred_full_col) or "").strip()
                            if pf_str:
                                # Try ISO then common formats
                                for fmt in (
                                    None,
                                    "%Y-%m-%d %H:%M:%S",
                                    "%Y-%m-%dT%H:%M:%S",
                                ):
                                    try:
                                        if fmt is None:
                                            pf_at = datetime.fromisoformat(pf_str)
                                        else:
                                            pf_at = datetime.strptime(pf_str, fmt)
                                        break
                                    except ValueError:
                                        continue

                        # 2) If we have prediction_ts + predicted_hrs_to_90,
                        #    compute predicted_full_at = ts + hours
                        if pf_at is None and pred_ts_col and pred_hrs_col:
                            ts_str = (row.get(pred_ts_col) or "").strip()
                            hrs_str = (row.get(pred_hrs_col) or "").strip()
                            if ts_str and hrs_str:
                                try:
                                    base_ts = datetime.fromisoformat(ts_str)
                                except ValueError:
                                    base_ts = None
                                try:
                                    hrs = float(hrs_str)
                                except ValueError:
                                    hrs = None

                                if base_ts is not None and hrs is not None:
                                    pf_at = base_ts + timedelta(hours=hrs)

                        pred = MLPrediction(
                            bin=bin_obj,
                            source="test",  # mark as test dataset predictions
                            predicted_fill_percent=fill_pct,
                            predicted_full_at=pf_at,
                        )
                        db.session.add(pred)
                        created_preds += 1

                    db.session.commit()
                    message = (
                        f"Uploaded successfully: {created_bins} bins, "
                        f"{created_preds} test predictions inserted."
                    )

            except Exception as e:
                db.session.rollback()
                error = f"Error while processing file: {e}"

    return render_template(
        "upload_test_predictions.html",
        message=message,
        error=error,
    )

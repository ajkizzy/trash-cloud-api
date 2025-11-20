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
                # Wrap the uploaded file as text for csv.DictReader
                text_stream = io.TextIOWrapper(
                    file.stream, encoding="utf-8", newline=""
                )
                reader = csv.DictReader(text_stream)

                created_bins = 0
                created_preds = 0

                for row in reader:
                    bin_code = row.get("bin_id")
                    if not bin_code:
                        continue

                    # Find or create bin
                    bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()
                    if not bin_obj:
                        bin_obj = Bin(trash_can_id=bin_code)
                        db.session.add(bin_obj)
                        created_bins += 1

                    # Current fill %
                    try:
                        fill_pct = float(row.get("current_fill_pct") or 0)
                    except ValueError:
                        fill_pct = 0.0

                    # Predicted full timestamp
                    pf_str = row.get("predicted_full_at") or ""
                    pf_at = None
                    if pf_str:
                        # Try ISO first, then a couple of common formats
                        tried = False
                        try:
                            pf_at = datetime.fromisoformat(pf_str)
                            tried = True
                        except ValueError:
                            pass

                        if not tried:
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                                try:
                                    pf_at = datetime.strptime(pf_str, fmt)
                                    break
                                except ValueError:
                                    continue

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

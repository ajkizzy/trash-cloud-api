from flask import Blueprint, request, jsonify, send_file, render_template_string, abort
import csv
import os
from datetime import datetime
import zipfile
import io

logs_bp = Blueprint("logs", __name__)

LOG_DIR = "trash_logs"
os.makedirs(LOG_DIR, exist_ok=True)


@logs_bp.route("/")
def index():
    files = sorted(os.listdir(LOG_DIR))
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Trash Cloud API</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
        rel="stylesheet"
      />
    </head>
    <body class="bg-dark text-light">
      <div class="container py-4">
        <h1 class="mb-3">Trash Cloud API</h1>
        <p class="mb-4">
          This service stores trash logs from devices and exposes a demo dashboard
          for the rubbish collector.
        </p>

        <a href="/dashboard" class="btn btn-success mb-4">Open Dashboard</a>

        <h3>Available log files</h3>
        <ul>
        {% for f in files %}
          <li>
            <a href="/view/{{ f }}">{{ f }}</a>
            &nbsp; - &nbsp;
            <a href="/download/{{ f }}">download</a>
          </li>
        {% else %}
          <li>No log files yet.</li>
        {% endfor %}
        </ul>

        <p class="mt-4 text-secondary">
          Devices can POST data to <code>/add_data</code> (JSON) to append to today&apos;s log.
        </p>
      </div>
    </body>
    </html>
    """
    return render_template_string(html, files=files)


@logs_bp.route("/add_data", methods=["GET", "POST"])
def add_data():
    if request.method == "GET":
        return jsonify(
            {
                "message": "POST JSON with trash_can_id, weight, timestamp to this endpoint."
            }
        )

    data = request.get_json(silent=True) or {}
    trash_can_id = data.get("trash_can_id")
    weight = data.get("weight")
    ts_str = data.get("timestamp")

    if not trash_can_id or weight is None:
        return jsonify({"error": "trash_can_id and weight are required"}), 400

    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str)
        except Exception:
            ts = datetime.utcnow()
    else:
        ts = datetime.utcnow()

    date_str = ts.strftime("%Y-%m-%d")
    filename = f"trash_{date_str}.csv"
    path = os.path.join(LOG_DIR, filename)

    file_exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "trash_can_id", "weight"])
        writer.writerow([ts.isoformat(), trash_can_id, weight])

    return jsonify({"status": "ok", "file": filename})


@logs_bp.route("/view/<filename>")
def view_file(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        abort(404)

    rows = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>View log {{ filename }}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
        rel="stylesheet"
      />
    </head>
    <body class="bg-dark text-light">
      <div class="container py-4">
        <h2>Log file: {{ filename }}</h2>
        <a href="/" class="btn btn-secondary btn-sm mb-3">Back</a>
        <div class="table-responsive">
          <table class="table table-sm table-striped table-dark">
            {% for row in rows %}
              {% if loop.first %}
                <thead>
                  <tr>
                    {% for col in row %}
                      <th>{{ col }}</th>
                    {% endfor %}
                  </tr>
                </thead>
                <tbody>
              {% else %}
                  <tr>
                    {% for col in row %}
                      <td>{{ col }}</td>
                    {% endfor %}
                  </tr>
              {% endif %}
            {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </body>
    </html>
    """
    return render_template_string(html, filename=filename, rows=rows)


@logs_bp.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


@logs_bp.route("/download_all")
def download_all():
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in os.listdir(LOG_DIR):
            zf.write(os.path.join(LOG_DIR, file), file)
    mem_zip.seek(0)
    return send_file(mem_zip, as_attachment=True, download_name="all_trash_logs.zip")

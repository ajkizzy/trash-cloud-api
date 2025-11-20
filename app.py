from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template_string,
    abort,
)
import csv
import os
from datetime import datetime
import zipfile
import io

from flask_sqlalchemy import SQLAlchemy

# -------------------------------------------------
# Basic Flask setup
# -------------------------------------------------
app = Flask(__name__)

# Where CSV log files from devices are stored
LOG_DIR = "trash_logs"
os.makedirs(LOG_DIR, exist_ok=True)

# -------------------------------------------------
# Database (Render PostgreSQL via SQLAlchemy)
# -------------------------------------------------
database_url = os.environ.get("DATABASE_URL")

# Render often gives postgres:// but SQLAlchemy wants postgresql://
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# -------------------------------------------------
# DB Models
# -------------------------------------------------
class Bin(db.Model):
    __tablename__ = "bins"

    id = db.Column(db.Integer, primary_key=True)
    trash_can_id = db.Column(db.String(64), unique=True, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    location_name = db.Column(db.String(120))
    capacity_litres = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)


class MLPrediction(db.Model):
    __tablename__ = "ml_predictions"

    id = db.Column(db.Integer, primary_key=True)
    bin_id = db.Column(db.Integer, db.ForeignKey("bins.id"), nullable=False)
    source = db.Column(db.String(32), nullable=False)  # "test" or "prototype"
    predicted_fill_percent = db.Column(db.Float, nullable=False)
    predicted_full_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bin = db.relationship("Bin", backref=db.backref("predictions", lazy=True))


class Route(db.Model):
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    source = db.Column(db.String(32), nullable=False)  # "test" or "prototype"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RouteStop(db.Model):
    __tablename__ = "route_stops"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(120))
    bin_id = db.Column(db.Integer, db.ForeignKey("bins.id"))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    distance_from_prev_km = db.Column(db.Float)
    est_travel_time_min = db.Column(db.Float)

    route = db.relationship(
        "Route",
        backref=db.backref("stops", order_by="RouteStop.order_index", lazy=True),
    )
    bin = db.relationship("Bin", backref=db.backref("route_stops", lazy=True))


# Create tables automatically (ok for prototype)
with app.app_context():
    db.create_all()


# -------------------------------------------------
# Simple index page (links to logs + dashboard)
# -------------------------------------------------
@app.route("/")
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
            &nbsp;–&nbsp;
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


# -------------------------------------------------
# Simple ingestion endpoint for prototype logging
# -------------------------------------------------
@app.route("/add_data", methods=["GET", "POST"])
def add_data():
    """
    POST JSON like:
    {
      "trash_can_id": "bin_1",
      "weight": 3.2,
      "timestamp": "2025-11-20T03:10:00"
    }
    Data is appended to a CSV file in trash_logs/.
    """
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


# -------------------------------------------------
# View a CSV log file in browser
# -------------------------------------------------
@app.route("/view/<filename>")
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


# -------------------------------------------------
# Download a single log file
# -------------------------------------------------
@app.route("/download/<filename>")
def download_file(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


# -------------------------------------------------
# Download all logs as ZIP
# -------------------------------------------------
@app.route("/download_all")
def download_all():
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in os.listdir(LOG_DIR):
            zf.write(os.path.join(LOG_DIR, file), file)
    mem_zip.seek(0)
    return send_file(mem_zip, as_attachment=True, download_name="all_trash_logs.zip")


# -------------------------------------------------
# API endpoints for dashboard
# -------------------------------------------------
@app.route("/api/predictions")
def api_predictions():
    """
    Returns prediction rows for either:
    - source=test
    - source=prototype
    """
    source = request.args.get("source", "test")

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


@app.route("/api/route")
def api_route():
    """
    Returns the latest route for a source (test/prototype)
    """
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


# -------------------------------------------------
# 3-tab dashboard (HTML + Leaflet + Bootstrap)
# -------------------------------------------------
@app.route("/dashboard")
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Smart Waste Collection Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">

        <!-- Bootstrap CSS -->
        <link
          href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
          rel="stylesheet"
        >
        <!-- Leaflet CSS -->
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        />

        <style>
          body { background:#111; color:#eee; padding:20px; }
          .nav-tabs .nav-link { color:#aaa; }
          .nav-tabs .nav-link.active { color:#fff; background:#222; }
          .card { background:#1b1b1b; border:none; }
          table { color:#eee; }
          #route-map { height:400px; border-radius:8px; overflow:hidden; margin-top:10px; }
        </style>
    </head>
    <body>
      <div class="container-fluid">
        <h1 class="mb-3">Smart Waste Collection Dashboard</h1>
        <p class="text-secondary mb-4">
          Demo dashboard for rubbish collectors – test dataset and prototype predictions.
        </p>

        <!-- Tabs -->
        <ul class="nav nav-tabs" id="dashboardTabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="tab-test-pred" data-bs-toggle="tab"
                    data-bs-target="#panel-test-pred" type="button" role="tab">
              1. Bins predicted full soon (Test dataset)
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-route" data-bs-toggle="tab"
                    data-bs-target="#panel-route" type="button" role="tab">
              2. Optimal Route (Test dataset)
            </button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="tab-proto-pred" data-bs-toggle="tab"
                    data-bs-target="#panel-proto-pred" type="button" role="tab">
              3. Prototype Predictions
            </button>
          </li>
        </ul>

        <div class="tab-content mt-3">
          <!-- Tab 1: Test predictions -->
          <div class="tab-pane fade show active" id="panel-test-pred" role="tabpanel">
            <div class="card">
              <div class="card-body">
                <h4 class="card-title">Bins predicted to be full soon (Test)</h4>
                <p class="text-secondary">Sorted by predicted full time / highest fill level.</p>
                <div class="table-responsive">
                  <table class="table table-sm table-striped table-dark align-middle">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Bin ID</th>
                        <th>Location</th>
                        <th>Fill %</th>
                        <th>Predicted full at</th>
                      </tr>
                    </thead>
                    <tbody id="test-predictions-body">
                      <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <!-- Tab 2: Route -->
          <div class="tab-pane fade" id="panel-route" role="tabpanel">
            <div class="card">
              <div class="card-body">
                <h4 class="card-title">Most optimal route (Test)</h4>
                <p class="text-secondary">Based on ML predictions for the test dataset.</p>
                <div id="route-map"></div>
                <div class="mt-3 table-responsive">
                  <table class="table table-sm table-striped table-dark align-middle">
                    <thead>
                      <tr>
                        <th>Stop</th>
                        <th>Label</th>
                        <th>Bin ID</th>
                        <th>Distance from previous (km)</th>
                        <th>Est. travel time (min)</th>
                      </tr>
                    </thead>
                    <tbody id="route-stops-body">
                      <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

          <!-- Tab 3: Prototype predictions -->
          <div class="tab-pane fade" id="panel-proto-pred" role="tabpanel">
            <div class="card">
              <div class="card-body">
                <h4 class="card-title">Prototype bin predictions</h4>
                <p class="text-secondary">Live / prototype data predictions.</p>
                <div class="table-responsive">
                  <table class="table table-sm table-striped table-dark align-middle">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Bin ID</th>
                        <th>Location</th>
                        <th>Fill %</th>
                        <th>Predicted full at</th>
                      </tr>
                    </thead>
                    <tbody id="proto-predictions-body">
                      <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- JS: Bootstrap, Leaflet -->
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

      <script>
        async function loadPredictions(source, tbodyId) {
          const tbody = document.getElementById(tbodyId);
          tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';

          try {
            const res = await fetch('/api/predictions?source=' + encodeURIComponent(source));
            const data = await res.json();

            if (!Array.isArray(data) || data.length === 0) {
              tbody.innerHTML = '<tr><td colspan="5">No prediction data found.</td></tr>';
              return;
            }

            tbody.innerHTML = '';
            data.forEach((row, idx) => {
              const tr = document.createElement('tr');
              tr.innerHTML = `
                <td>${idx + 1}</td>
                <td>${row.bin_id || '-'}</td>
                <td>${row.location_name || '-'}</td>
                <td>${row.predicted_fill_percent != null ? row.predicted_fill_percent.toFixed(1) + '%' : '-'}</td>
                <td>${row.predicted_full_at || '-'}</td>
              `;
              tbody.appendChild(tr);
            });
          } catch (err) {
            console.error(err);
            tbody.innerHTML = '<tr><td colspan="5">Error loading data.</td></tr>';
          }
        }

        let map;
        let routeLayer;

        function initMap() {
          map = L.map('route-map').setView([0, 0], 2);
          L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
          }).addTo(map);
        }

        async function loadRoute(source) {
          const tbody = document.getElementById('route-stops-body');
          tbody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';

          try {
            const res = await fetch('/api/route?source=' + encodeURIComponent(source));
            const data = await res.json();

            const stops = data.stops || [];
            if (stops.length === 0) {
              tbody.innerHTML = '<tr><td colspan="5">No route data found.</td></tr>';
              return;
            }

            tbody.innerHTML = '';

            // Clear previous route from map
            if (routeLayer) {
              routeLayer.remove();
            }

            const latlngs = [];

            stops.forEach((s, idx) => {
              const tr = document.createElement('tr');
              tr.innerHTML = `
                <td>${idx + 1}</td>
                <td>${s.label || '-'}</td>
                <td>${s.bin_id || '-'}</td>
                <td>${s.distance_from_prev_km != null ? s.distance_from_prev_km.toFixed(2) : '-'}</td>
                <td>${s.est_travel_time_min != null ? s.est_travel_time_min.toFixed(1) : '-'}</td>
              `;
              tbody.appendChild(tr);

              if (s.lat != null && s.lon != null) {
                const ll = [s.lat, s.lon];
                latlngs.push(ll);
                L.marker(ll).addTo(map).bindPopup((s.label || 'Stop') + '<br>Bin: ' + (s.bin_id || '-'));
              }
            });

            if (latlngs.length > 0) {
              routeLayer = L.polyline(latlngs, { weight: 4 }).addTo(map);
              map.fitBounds(routeLayer.getBounds().pad(0.25));
            }
          } catch (err) {
            console.error(err);
            tbody.innerHTML = '<tr><td colspan="5">Error loading route.</td></tr>';
          }
        }

        document.addEventListener('DOMContentLoaded', () => {
          initMap();
          loadPredictions('test', 'test-predictions-body');
          loadPredictions('prototype', 'proto-predictions-body');
          loadRoute('test');
        });
      </script>
    </body>
    </html>
    """
    return render_template_string(html)


# -------------------------------------------------
# Local dev entrypoint (Render uses gunicorn app:app)
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

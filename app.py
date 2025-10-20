# Simple Flask API + Dashboard for Trash Can Data
from flask import Flask, request, jsonify, send_file, render_template_string
import csv
import os
from datetime import datetime

app = Flask(__name__)
CSV_FILE = 'trash_data.csv'

def init_csv():
    """Initialize CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['timestamp', 'trash_can_id', 'fill_level'])

init_csv()

@app.route('/')
def index():
    return "Trash Can Data API is running. Visit /dashboard to view logs."

@app.route('/add_data', methods=['POST'])
def add_data():
    """Add new trash can data to the CSV."""
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400

    timestamp = data.get('timestamp', datetime.now().isoformat())
    trash_can_id = data.get('trash_can_id', 'unknown')

    try:
        fill_level = int(data.get('fill_level', 0))
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'fill_level must be an integer'}), 400

    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, trash_can_id, fill_level])

    return jsonify({'status': 'success', 'timestamp': timestamp}), 200

@app.route('/download', methods=['GET'])
def download_csv():
    """Download the CSV file."""
    if not os.path.exists(CSV_FILE):
        return jsonify({'status': 'error', 'message': 'CSV file not found'}), 404
    return send_file(CSV_FILE, as_attachment=True)

@app.route('/dashboard')
def dashboard():
    """Render an HTML dashboard of recent readings."""
    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='') as file:
            reader = csv.DictReader(file)
            rows = list(reader)

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Trash Bin Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: sans-serif; margin: 40px; background: #111; color: white; }
            h1 { color: #6cf; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #333; padding: 8px; text-align: center; }
            tr:nth-child(even) { background: #222; }
            canvas { margin-top: 30px; width: 100%; max-height: 400px; }
        </style>
    </head>
    <body>
        <h1>Trash Bin Dashboard</h1>
        <p>Live data from all bins. Last update: {{ rows[-1]['timestamp'] if rows else 'No data yet' }}</p>
        <canvas id="chart"></canvas>
        <table>
            <tr><th>Timestamp</th><th>Bin ID</th><th>Fill Level (%)</th></tr>
            {% for row in rows[-30:] %}
                <tr><td>{{ row['timestamp'] }}</td><td>{{ row['trash_can_id'] }}</td><td>{{ row['fill_level'] }}</td></tr>
            {% endfor %}
        </table>
        <script>
            const data = {
                labels: {{ rows[-30:] | map(attribute='timestamp') | list | safe }},
                datasets: [{
                    label: 'Fill Level (%)',
                    data: {{ rows[-30:] | map(attribute='fill_level') | list | safe }},
                    borderColor: '#6cf',
                    backgroundColor: '#6cf2',
                    fill: true,
                    tension: 0.3
                }]
            };
            new Chart(document.getElementById('chart'), {
                type: 'line',
                data: data,
                options: { scales: { y: { min: 0, max: 100 } } }
            });
        </script>
    </body>
    </html>
    """

    return render_template_string(html, rows=rows)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

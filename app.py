# Simple Flask API to receive trash can data and store it in a CSV
from flask import Flask, request, jsonify, send_file
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


@app.route('/', methods=['GET'])
def index():
    return "Trash Can Data API is running. POST data to /add_data endpoint."


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

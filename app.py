# Simple Flask API to receive trash can data and store it in a CSV
from flask import Flask, request, jsonify
import csv
import os
from datetime import datetime

from flask import send_file

@app.route('/download', methods=['GET'])
def download_csv():
    return send_file('trash_data.csv', as_attachment=True)

app = Flask(__name__)
CSV_FILE = 'trash_data.csv'

# Initialize CSV file if it doesn't exist
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['timestamp', 'trash_can_id', 'fill_level'])

@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.get_json()
    timestamp = data.get('timestamp', datetime.now().isoformat())
    trash_can_id = data.get('trash_can_id', 'unknown')
    fill_level = data.get('fill_level', 0)
    
    with open(CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, trash_can_id, fill_level])
    
    return jsonify({'status': 'success', 'timestamp': timestamp}), 200

@app.route('/', methods=['GET'])
def index():
    return "Trash Can Data API is running. POST data to /add_data endpoint."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

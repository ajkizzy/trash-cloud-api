from flask import Flask, request, jsonify, send_file, render_template_string, abort
import csv
import os
from datetime import datetime
import zipfile
import io

app = Flask(__name__)
LOG_DIR = "trash_logs"
os.makedirs(LOG_DIR, exist_ok=True)


@app.route('/')
def index():
    files = sorted(os.listdir(LOG_DIR))
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trash Logs Dashboard</title>
        <style>
            body { font-family: Arial; background: #111; color: white; margin: 40px; }
            h1 { color: #6cf; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #333; padding: 8px; text-align: left; }
            tr:nth-child(even) { background: #222; }
            a.button {
                display: inline-block; padding: 6px 12px;
                color: white; background: #6cf; border-radius: 4px;
                text-decoration: none; font-weight: bold;
            }
            a.button:hover { background: #4af; }
        </style>
    </head>
    <body>
        <h1>Trash Bin Logs</h1>
        <p>Below are all available log files stored on Render.</p>
        <table>
            <tr><th>Filename</th><th>Actions</th></tr>
            {% for file in files %}
                <tr>
                    <td>{{ file }}</td>
                    <td>
                        <a class="button" href="/view/{{ file }}">View</a>
                        <a class="button" href="/download/{{ file }}">Download</a>
                    </td>
                </tr>
            {% endfor %}
        </table>
        <br>
        <a class="button" href="/download_all">Download All Logs (ZIP)</a>
    </body>
    </html>
    """
    return render_template_string(html, files=files)


@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400

    timestamp = data.get('timestamp', datetime.now().isoformat())
    trash_can_id = data.get('trash_can_id', 'unknown')
    fill_level = data.get('fill_level', 0)

    filename = f"trash_{datetime.now().date()}.csv"
    path = os.path.join(LOG_DIR, filename)

    write_header = not os.path.exists(path)
    with open(path, 'a', newline='') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(['timestamp', 'trash_can_id', 'fill_level'])
        writer.writerow([timestamp, trash_can_id, fill_level])

    return jsonify({'status': 'success', 'saved_to': filename}), 200


@app.route('/view/<filename>')
def view_log(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        abort(404)

    with open(path, newline='') as f:
        rows = list(csv.reader(f))

    html = """
    <html>
    <head>
        <title>{{ filename }}</title>
        <style>
            body { background: #111; color: white; font-family: monospace; margin: 30px; }
            h2 { color: #6cf; }
            table { border-collapse: collapse; width: 100%; margin-top: 10px; }
            th, td { border: 1px solid #333; padding: 6px; text-align: left; }
            tr:nth-child(even) { background: #222; }
            a { color: #6cf; text-decoration: none; }
        </style>
    </head>
    <body>
        <h2>{{ filename }}</h2>
        <table>
            {% for row in rows %}
                <tr>{% for cell in row %}<td>{{ cell }}</td>{% endfor %}</tr>
            {% endfor %}
        </table>
        <br><a href="/">← Back</a>
    </body>
    </html>
    """
    return render_template_string(html, filename=filename, rows=rows)


@app.route('/download/<filename>')
def download_file(filename):
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=True)


@app.route('/download_all')
def download_all():
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in os.listdir(LOG_DIR):
            zf.write(os.path.join(LOG_DIR, file), file)
    mem_zip.seek(0)
    return send_file(mem_zip, as_attachment=True, download_name="all_trash_logs.zip")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

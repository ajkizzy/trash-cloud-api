from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from config import Config

# --- Initialise DB ---
db = SQLAlchemy()


# --- Import blueprints (AFTER db is created but BEFORE app factory) ---
from api import api_bp
from upload_test_predictions import upload_test_predictions_bp
from upload_route_test import upload_route_test_bp     # ← NEW BLUEPRINT


# --- Application Factory ---
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialise extensions
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(upload_test_predictions_bp)
    app.register_blueprint(upload_route_test_bp)       # ← REGISTER HERE

    # Default route → Dashboard
    @app.route("/")
    def index():
        return render_template("dashboard.html")

    return app


# --- Gunicorn entrypoint ---
app = create_app()


# --- Enable CLI DB creation (optional) ---
@app.cli.command("create-db")
def create_db():
    db.create_all()
    print("Database tables created")

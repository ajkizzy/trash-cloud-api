import os
from flask import Flask
from extensions import db


def create_app() -> Flask:
    app = Flask(__name__)

    # Database configuration from environment (Render)
    database_url = os.environ.get("DATABASE_URL")

    # Render often provides postgres:// but SQLAlchemy expects postgresql://
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize SQLAlchemy extension
    db.init_app(app)

    with app.app_context():
        # Import models so SQLAlchemy knows about them
        from models import Bin, MLPrediction, Route, RouteStop  # noqa: F401

        # Create tables if they do not exist yet (good enough for prototype)
        db.create_all()

        # Register blueprints
        from routes.logs import logs_bp
        from routes.api import api_bp
        from routes.dashboard import dashboard_bp
        from routes.upload import upload_bp
        from routes.upload_route import upload_route_bp

        app.register_blueprint(logs_bp)
        app.register_blueprint(api_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(upload_bp)
        app.register_blueprint(upload_route_bp)

    return app


# Gunicorn on Render uses this object
app = create_app()


if __name__ == "__main__":
    # Local development entrypoint
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    

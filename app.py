import os
from flask import Flask
from extensions import db


def create_app():
    app = Flask(__name__)

    # Database config from Render
    database_url = os.environ.get("DATABASE_URL")
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        # Import models so SQLAlchemy knows them
        from models import Bin, MLPrediction, Route, RouteStop  # noqa
        db.create_all()

        # Register blueprints
        from routes.logs import logs_bp
        from routes.api import api_bp
        from routes.dashboard import dashboard_bp

        app.register_blueprint(logs_bp)
        app.register_blueprint(api_bp)
        app.register_blueprint(dashboard_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

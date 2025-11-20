from datetime import datetime
from extensions import db


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

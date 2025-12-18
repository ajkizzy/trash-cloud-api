from flask import Blueprint, render_template, request, jsonify
from extensions import db
from models import Bin, Route, RouteStop, MLPrediction
import csv
import io

# This blueprint is mounted with url_prefix="/dev" in app.py
upload_route_bp = Blueprint("upload_route", __name__, url_prefix="/dev")


@upload_route_bp.route("/upload_route_test", methods=["GET", "POST"])
def upload_route_test():
    """
    Upload a CSV containing an optimal route OR generate route from predictions.
    
    Two modes:
    1. Upload CSV with route data
    2. Auto-generate route from existing predictions using KNN
    """
    message = None
    error = None

    if request.method == "POST":
        # Check if user wants to generate route automatically
        auto_generate = request.form.get("auto_generate") == "true"
        
        if auto_generate:
            try:
                # Generate route from predictions
                from route_optimizer import RouteOptimizer
                
                # Get all test predictions with coordinates
                predictions = (
                    MLPrediction.query
                    .join(Bin)
                    .filter(MLPrediction.source == "test")
                    .filter(Bin.latitude.isnot(None))
                    .filter(Bin.longitude.isnot(None))
                    .order_by(MLPrediction.predicted_fill_percent.desc())
                    .all()
                )
                
                if not predictions:
                    error = "No predictions found with coordinates. Upload predictions first."
                    return render_template("upload_route_test.html", message=message, error=error)
                
                # Prepare bin data for optimizer
                bins = []
                for pred in predictions:
                    bins.append({
                        'bin_id': pred.bin.trash_can_id,
                        'lat': pred.bin.latitude,
                        'lon': pred.bin.longitude,
                        'predicted_fill_percent': pred.predicted_fill_percent
                    })
                
                # Get depot coordinates (use first bin or default)
                depot_lat = float(request.form.get("depot_lat", bins[0]['lat'] if bins else 0))
                depot_lon = float(request.form.get("depot_lon", bins[0]['lon'] if bins else 0))
                threshold = float(request.form.get("threshold", 70.0))
                
                # Initialize optimizer and generate route
                optimizer = RouteOptimizer(depot_lat, depot_lon)
                route_stops = optimizer.optimize_route(bins, priority_threshold=threshold)
                
                if not route_stops:
                    error = f"No bins found above {threshold}% fill level."
                    return render_template("upload_route_test.html", message=message, error=error)
                
                # Clear existing test routes
                existing_routes = Route.query.filter_by(source="test").all()
                for r in existing_routes:
                    RouteStop.query.filter_by(route_id=r.id).delete()
                    db.session.delete(r)
                
                # Create new route
                stats = optimizer.calculate_route_stats(route_stops)
                route_name = f"Auto Route (Test) - {stats['total_stops']} bins"
                
                route_obj = Route(name=route_name, source="test")
                db.session.add(route_obj)
                db.session.flush()
                
                # Add stops
                for stop_data in route_stops:
                    bin_obj = None
                    if stop_data['bin_id']:
                        bin_obj = Bin.query.filter_by(trash_can_id=stop_data['bin_id']).first()
                    
                    stop = RouteStop(
                        route_id=route_obj.id,
                        order_index=stop_data['order_index'],
                        label=stop_data['label'],
                        bin=bin_obj,
                        latitude=stop_data['lat'],
                        longitude=stop_data['lon'],
                        distance_from_prev_km=stop_data['distance_from_prev_km'],
                        est_travel_time_min=stop_data['est_travel_time_min']
                    )
                    db.session.add(stop)
                
                db.session.commit()
                
                message = (
                    f"Generated optimal route with {stats['total_stops']} bins. "
                    f"Total distance: {stats['total_distance_km']} km, "
                    f"Est. time: {stats['total_time_hours']} hours"
                )
                
            except Exception as e:
                db.session.rollback()
                error = f"Error generating route: {e}"
        
        else:
            # Upload CSV mode
            file = request.files.get("file") or request.files.get("csv_file")

            if not file or file.filename == "":
                error = "Please choose a CSV file to upload."
            else:
                try:
                    text_stream = io.TextIOWrapper(file.stream, encoding="utf-8", newline="")
                    reader = csv.DictReader(text_stream)

                    required_cols = [
                        "order_index", "bin_id", "lat", "lon",
                        "distance_from_prev_km", "est_travel_time_min"
                    ]
                    
                    missing_cols = [col for col in required_cols if col not in reader.fieldnames]
                    if missing_cols:
                        raise ValueError(f"Missing columns: {', '.join(missing_cols)}")

                    # Clear existing test routes
                    existing_routes = Route.query.filter_by(source="test").all()
                    for r in existing_routes:
                        RouteStop.query.filter_by(route_id=r.id).delete()
                        db.session.delete(r)
                    
                    route_name = request.form.get("route_name", "Uploaded Test Route")
                    route_obj = Route(name=route_name, source="test")
                    db.session.add(route_obj)
                    db.session.flush()

                    stop_count = 0
                    for row in reader:
                        bin_code = (row.get("bin_id") or "").strip()
                        
                        try:
                            order_index = int(row.get("order_index") or 0)
                        except ValueError:
                            order_index = stop_count

                        try:
                            lat = float(row.get("lat") or 0)
                            lon = float(row.get("lon") or 0)
                            dist_km = float(row.get("distance_from_prev_km") or 0)
                            travel_min = float(row.get("est_travel_time_min") or 0)
                        except ValueError as e:
                            raise ValueError(f"Invalid numeric value in row {stop_count + 1}: {e}")

                        bin_obj = None
                        if bin_code:
                            bin_obj = Bin.query.filter_by(trash_can_id=bin_code).first()

                        label = row.get("label", f"Bin {bin_code}" if bin_code else f"Stop {order_index}")

                        stop = RouteStop(
                            route_id=route_obj.id,
                            order_index=order_index,
                            label=label,
                            bin=bin_obj,
                            latitude=lat,
                            longitude=lon,
                            distance_from_prev_km=dist_km,
                            est_travel_time_min=travel_min
                        )
                        db.session.add(stop)
                        stop_count += 1

                    if stop_count == 0:
                        error = "No valid rows found in CSV."
                        db.session.rollback()
                    else:
                        db.session.commit()
                        message = f"Uploaded route '{route_obj.name}' with {stop_count} stops."

                except Exception as e:
                    db.session.rollback()
                    error = f"Error processing CSV: {e}"

    return render_template("upload_route_test.html", message=message, error=error)


@upload_route_bp.route("/generate_route_api", methods=["POST"])
def generate_route_api():
    """API endpoint to generate route programmatically."""
    try:
        data = request.get_json() or {}
        depot_lat = float(data.get("depot_lat", 0))
        depot_lon = float(data.get("depot_lon", 0))
        threshold = float(data.get("threshold", 70.0))
        source = data.get("source", "test")
        
        from route_optimizer import RouteOptimizer
        
        predictions = (
            MLPrediction.query
            .join(Bin)
            .filter(MLPrediction.source == source)
            .filter(Bin.latitude.isnot(None))
            .filter(Bin.longitude.isnot(None))
            .all()
        )
        
        bins = [{
            'bin_id': p.bin.trash_can_id,
            'lat': p.bin.latitude,
            'lon': p.bin.longitude,
            'predicted_fill_percent': p.predicted_fill_percent
        } for p in predictions]
        
        optimizer = RouteOptimizer(depot_lat, depot_lon)
        route_stops = optimizer.optimize_route(bins, priority_threshold=threshold)
        stats = optimizer.calculate_route_stats(route_stops)
        
        return jsonify({
            "success": True,
            "route": route_stops,
            "stats": stats
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400
@upload_route_bp.route("/generate_prototype_route", methods=["POST"])
def generate_prototype_route():
    """Generate route for prototype bins."""
    try:
        data = request.get_json() or {}
        depot_lat = float(data.get("depot_lat", 55.6761))
        depot_lon = float(data.get("depot_lon", 12.5683))
        threshold = float(data.get("threshold", 70.0))
        
        from route_optimizer import RouteOptimizer
        
        # Get prototype predictions
        predictions = (
            MLPrediction.query
            .join(Bin)
            .filter(MLPrediction.source == "prototype")
            .filter(Bin.latitude.isnot(None))
            .filter(Bin.longitude.isnot(None))
            .all()
        )
        
        if not predictions:
            return jsonify({"success": False, "error": "No prototype predictions found"}), 404
        
        bins = [{
            'bin_id': p.bin.trash_can_id,
            'lat': p.bin.latitude,
            'lon': p.bin.longitude,
            'predicted_fill_percent': p.predicted_fill_percent
        } for p in predictions]
        
        optimizer = RouteOptimizer(depot_lat, depot_lon)
        route_stops = optimizer.optimize_route(bins, priority_threshold=threshold)
        
        if not route_stops:
            return jsonify({"success": False, "error": f"No bins above {threshold}% threshold"}), 404
        
        # Clear old prototype routes
        existing_routes = Route.query.filter_by(source="prototype").all()
        for r in existing_routes:
            RouteStop.query.filter_by(route_id=r.id).delete()
            db.session.delete(r)
        
        # Create new route
        stats = optimizer.calculate_route_stats(route_stops)
        route_obj = Route(name=f"Prototype Route - {stats['total_stops']} bins", source="prototype")
        db.session.add(route_obj)
        db.session.flush()
        
        # Add stops
        for stop_data in route_stops:
            bin_obj = None
            if stop_data['bin_id']:
                bin_obj = Bin.query.filter_by(trash_can_id=stop_data['bin_id']).first()
            
            stop = RouteStop(
                route_id=route_obj.id,
                order_index=stop_data['order_index'],
                label=stop_data['label'],
                bin=bin_obj,
                latitude=stop_data['lat'],
                longitude=stop_data['lon'],
                distance_from_prev_km=stop_data['distance_from_prev_km'],
                est_travel_time_min=stop_data['est_travel_time_min']
            )
            db.session.add(stop)
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "route": route_stops,
            "stats": stats
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

# Smart Waste Collection System

A Flask-based web application for optimizing waste collection routes using machine learning predictions and KNN-based route optimization.

## System Overview

This system receives waste bin fill level predictions, stores them in a PostgreSQL database, and generates optimal collection routes using a K-Nearest Neighbor (KNN) algorithm. It supports both test datasets and real-time prototype data from IoT sensors.

## Features

- **ML Prediction Management**: Upload and view waste bin fill level predictions
- **Route Optimization**: Auto-generate optimal collection routes using KNN algorithm
- **Interactive Dashboard**: Three-tab interface for test data, routes, and live prototype monitoring
- **Real-time Data**: API endpoint for Raspberry Pi sensors to submit live bin data
- **Map Visualization**: Interactive Leaflet maps showing bin locations and collection routes
- **Auto-refresh**: Live updates for prototype predictions every 30 seconds

## Project Structure

```
.
├── app.py                          # Flask application entry point
├── extensions.py                   # SQLAlchemy database instance
├── models.py                       # Database models (Bin, MLPrediction, Route, RouteStop)
├── route_optimizer.py              # KNN-based route optimization algorithm
├── requirements.txt                # Python dependencies
├── Procfile                        # Render deployment configuration
│
├── routes/                         # Blueprint modules
│   ├── __init__.py
│   ├── api.py                      # REST API endpoints
│   ├── dashboard.py                # Dashboard page route
│   ├── logs.py                     # Legacy logging endpoints
│   ├── upload.py                   # CSV upload handlers
│   └── upload_route.py             # Route generation and upload
│
└── templates/                      # HTML templates
    ├── base.html                   # Base template with styling
    ├── dashboard.html              # Main dashboard interface
    ├── upload_test_predictions.html
    └── upload_route_test.html
```

## Core Components

### 1. Database Models (`models.py`)

- **Bin**: Stores waste bin information (ID, location, capacity)
- **MLPrediction**: Stores fill level predictions with timestamps
- **Route**: Metadata for collection routes
- **RouteStop**: Individual stops in a route with distance/time calculations

### 2. Route Optimizer (`route_optimizer.py`)

Implements a greedy nearest-neighbor algorithm (KNN with K=1):
- Filters bins above a fill threshold
- Starts from depot location
- Repeatedly selects the nearest unvisited bin
- Calculates distances using Haversine formula
- Returns to depot at the end

### 3. API Endpoints (`routes/api.py`)

- `GET /api/predictions?source=test|prototype` - Retrieve predictions
- `GET /api/route?source=test|prototype` - Get latest route
- `POST /api/prototype/submit` - Submit live data from Raspberry Pi
- `GET /api/health` - Health check

### 4. Dashboard (`templates/dashboard.html`)

Three-tab interface:
1. **Predictions (Test)**: View uploaded test predictions
2. **Optimal Route (Test)**: Auto-generated or uploaded routes with map
3. **Prototype Predictions**: Live data from IoT sensors with route generation

### 5. Upload Routes (`routes/upload.py`, `routes/upload_route.py`)

- Upload prediction CSV files
- Upload pre-generated route CSV files
- Auto-generate routes using the KNN optimizer

## Setup and Installation

### Prerequisites

- Python 3.9+
- PostgreSQL database
- Environment variable `DATABASE_URL` pointing to PostgreSQL

### Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variable:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost/dbname"
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Access the dashboard at `http://localhost:5000/dashboard`

### Deployment (Render)

The application is configured for deployment on Render using the `Procfile`:
```
web: gunicorn app:app
```

Set the `DATABASE_URL` environment variable in Render's dashboard.

## CSV File Formats

### Predictions CSV (`predictions_test.csv`)

```csv
bin_id,lat,lon,location_name,current_fill_pct,predicted_full_at
BIN001,55.6800,12.5700,City Center,75.5,2025-12-25 14:30:00
BIN002,55.6820,12.5720,Park Area,82.3,2025-12-24 09:15:00
```

Required columns:
- `bin_id`: Unique bin identifier
- `lat`, `lon`: Coordinates
- `current_fill_pct`: Current fill percentage
- `predicted_full_at`: Timestamp when bin will be full (optional)

### Route CSV (`route_test_for_dashboard.csv`)

```csv
order_index,bin_id,lat,lon,distance_from_prev_km,est_travel_time_min,label
0,DEPOT,55.6761,12.5683,0.0,0.0,Depot Start
1,BIN001,55.6800,12.5700,0.5,1.0,Bin BIN001
2,BIN003,55.6820,12.5720,0.3,0.6,Bin BIN003
3,DEPOT,55.6761,12.5683,0.7,1.4,Depot End
```

## Raspberry Pi Integration

Send POST requests to `/api/prototype/submit` with JSON payload:

```json
{
  "bin_id": "BIN_RPI_001",
  "fill_percent": 75.5,
  "latitude": 55.6761,
  "longitude": 12.5683,
  "location_name": "Test Location",
  "capacity_litres": 120,
  "predicted_full_at": "2025-12-25 14:30:00"
}
```

Example Python code for Raspberry Pi:
```python
import requests
import json

data = {
    "bin_id": "BIN_RPI_001",
    "fill_percent": 75.5,
    "latitude": 55.6761,
    "longitude": 12.5683
}

response = requests.post(
    "https://your-app.onrender.com/api/prototype/submit",
    json=data
)
print(response.json())
```

## Route Optimization Algorithm

The system uses a greedy nearest-neighbor approach:

1. **Filtering**: Select bins above threshold (default 70-80%)
2. **Initialization**: Start at depot coordinates
3. **Selection Loop**: 
   - Find nearest unvisited bin using Haversine distance
   - Add to route
   - Update current position
4. **Return**: Calculate return trip to depot
5. **Statistics**: Total distance, time, and stop count

**Assumptions**:
- Average vehicle speed: 30 km/h
- Direct-line distances (Haversine formula)
- No traffic or road constraints


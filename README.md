File Explanations

    app.py

Creates the Flask application, configures the database, and registers all route modules (blueprints).

  extensions.py

Stores the shared SQLAlchemy db object so models and routes can access it cleanly.

    models.py

Defines all database models:
	•	Bin – information about each trash bin
	•	MLPrediction – predicted fill levels & timestamps
	•	Route – optimal route metadata
	•	RouteStop – each stop in a route, with coordinates & order

    routes/

routes/logs.py

Endpoints for:
	•	Receiving sensor data (/add_data)
	•	Saving logs into CSV files
	•	Viewing and downloading CSV logs

routes/api.py

Backend API used by the dashboard:
	•	/api/predictions – ML prediction data
	•	/api/route – optimal route information

routes/dashboard.py

Serves the dashboard HTML page at /dashboard.

routes/init.py

Makes the routes/ folder a Python package.

  templates/

templates/base.html

Shared base template that includes:
	•	Bootstrap
	•	Leaflet (map library)
	•	Styling and layout

templates/dashboard.html

Main frontend page containing:
	•	Prediction Tab
	•	Route Tab
	•	Prototype Tab
with JavaScript that loads data from /api/predictions and /api/route.


 Other Files

requirements.txt

Python dependencies for Flask, SQLAlchemy, psycopg2, etc.

Procfile

Tells Render how to start the app:

web: gunicorn app:app

#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\app.py
from flask import Flask
from dotenv import load_dotenv, find_dotenv
import os
from flask_jwt_extended import JWTManager
from db import db
from flask_migrate import Migrate
from flask_bootstrap import Bootstrap5
from apscheduler.schedulers.background import BackgroundScheduler

# from flask_socketio import SocketIO
# from pg_listener import PostgresListener
# import callbacks
# Import the initialization function from firebase_listener.py
from firebase_listener import init_firebase_listener


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("FLASK_KEY")
# socketio = SocketIO(app, cors_allowed_origins="*")

# --- Route Blueprints ---
from routes.inventory_containers_routes import inventory_container_api
from routes.control_routes import control_api
from routes.hardware_component_routes import hardware_components_api
from routes.user_routes import users_api
from routes.greenhouses_routes import greenhouses_api
from routes.harvests_routes import harvests_api
from routes.reason_for_rejection_routes import reason_for_rejection_api
from routes.admin_routes import admin_api
from routes.maintenance_routes import maintenance_api
from routes.activity_logs_routes import activity_logs_api
from routes.hardware_status_routes import hardware_status_api
from routes.email_sender_routes import email_sender_api
from routes.truncate_routes import truncate_api
from routes.nutrient_controllers_routes import nutrient_controllers_api
from routes.stored_email_routes import stored_email_api
from routes.verification_routes import verification_code_api
from routes.planted_crops_routes import planted_crops_api
from routes.inventory_routes import inventory_api
from routes.sales_routes import sale_api
from routes.sensor_readings_routes import sensor_readings_api, fetch_and_store_firebase_data
from routes.inventory_item_routes import inventory_item_api

app.register_blueprint(inventory_item_api)
app.register_blueprint(sale_api)
app.register_blueprint(control_api)
app.register_blueprint(users_api)
app.register_blueprint(greenhouses_api)
app.register_blueprint(harvests_api)
app.register_blueprint(reason_for_rejection_api)
app.register_blueprint(admin_api)
app.register_blueprint(maintenance_api)
app.register_blueprint(activity_logs_api)
app.register_blueprint(hardware_components_api)
app.register_blueprint(hardware_status_api)
app.register_blueprint(email_sender_api)
app.register_blueprint(truncate_api)
app.register_blueprint(nutrient_controllers_api)
app.register_blueprint(stored_email_api)
app.register_blueprint(verification_code_api)
app.register_blueprint(planted_crops_api)
app.register_blueprint(inventory_api)
app.register_blueprint(inventory_container_api)
app.register_blueprint(sensor_readings_api)

# --- Configuration and Extensions ---
load_dotenv(find_dotenv())
Bootstrap5(app)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///agreemo.db")
db.init_app(app)
migrate = Migrate(app, db)

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
jwt = JWTManager(app)

# --- Basic Routes ---
@app.route('/')
def index():
    return "Welcome to the Agreemo API!"

init_firebase_listener(app)

# --- Scheduler Setup ---
scheduler = BackgroundScheduler()
# IMPORTANT: Pass the Flask app context to the scheduled function
scheduler.add_job(func=lambda: fetch_and_store_firebase_data(app), trigger="interval", hours=2)
scheduler.start()


# --- Run Application ---
if __name__ == "__main__":
    app.run(debug=True, port=5028)
    # socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), allow_unsafe_werkzeug=True, debug=True)
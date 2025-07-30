#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\control_routes.py
import os
#import firebase_admin # No longer needed here
from firebase_admin import db #only import db
from flask import Blueprint, request, jsonify, current_app # Added current_app for potential logging
from dotenv import load_dotenv
import psycopg2 # Keep if used elsewhere, not directly used in these endpoints
from datetime import datetime
import pytz  # Import pytz

# Assuming ControlActivityLogs is correctly imported from your models
from models.activity_logs.control_activity_logs_model import ControlActivityLogs
# If using SQLAlchemy for logs, ensure db is imported from your app's db setup
from db import db as sqlalchemy_db


control_api = Blueprint("control_api", __name__)

load_dotenv()

API_KEY = os.environ.get("API_KEY")
# CREDENTIALS_PATH, DATABASE_URL, DB_URI not directly used in these functions anymore

PH_TZ = pytz.timezone('Asia/Manila') # Define timezone

# --- Helper Function for Date Formatting ---
def format_datetime(dt):
    """Formats datetime to YYYY-MM-DD HH:MM:SS AM/PM in PH Timezone."""
    if not dt: return None
    try:
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            # Assume naive datetimes from DB represent PH time
            aware_dt = PH_TZ.localize(dt)
        else:
            # Convert any aware datetime to PH_TZ
            aware_dt = dt.astimezone(PH_TZ)
        # Format to: Year-Month-Day Hour(12):Minute:Second AM/PM
        return aware_dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        # Log the error and return a fallback format
        # Use current_app.logger if Flask app context is available, otherwise print
        log_func = getattr(current_app, 'logger', None)
        if log_func:
            log_func.warning(f"Could not format datetime {dt}: {e}")
        else:
            print(f"Warning: Could not format datetime {dt}: {e}")
        try:
            return dt.isoformat() # Fallback to ISO format
        except:
            return str(dt) # Final fallback

# --- Helper Function to Log Changes (Using SQLAlchemy) ---
# (Keep this if you intend to log changes from a POST/PATCH endpoint later)
def log_control_change_db(pump1=None, pump2=None, exhaust=None, automode=None, description="Control values updated"):
    """Logs control changes to the PostgreSQL database via SQLAlchemy."""
    try:
        # Assuming ControlActivityLogs uses default timestamp
        log_entry = ControlActivityLogs(
            pump1=pump1,
            pump2=pump2,
            exhaust=exhaust,
            automode=automode,
            logs_description=description
            # log_date will use the default defined in the model
        )
        sqlalchemy_db.session.add(log_entry)
        sqlalchemy_db.session.commit() # Commit immediately for logging? Or handle in caller?
        if current_app:
            current_app.logger.info(f"Control change logged: {description}")
    except Exception as e:
        print(f"Error logging control change to DB: {e}") # Use print or logger
        sqlalchemy_db.session.rollback()


# --- GET Endpoint (Retrieve Current Control State from Firebase) ---
@control_api.route("/control", methods=['GET'])
def get_control():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        # Reference the specific path in Firebase RTDB
        ref = db.reference("pumpControl") # Or the correct path for your control data
        pump_data = ref.get()

        if pump_data is None:
            # It's better to return 200 OK with a message/empty object if data not existing isn't an error
            # return jsonify(message="No control data found in Firebase at 'pumpControl'"), 200
            # Or 404 if it's expected to exist
             return jsonify(error={"message": "Control data not found in Firebase at 'pumpControl'"}), 404


        # Log successful retrieval
        if current_app:
            current_app.logger.info("Successfully retrieved control data from Firebase.")

        return jsonify(pump_data), 200

    except Exception as e:
        # Log the error
        error_msg = f"Error getting control values from Firebase: {e}"
        if current_app:
            current_app.logger.error(error_msg, exc_info=True)
        else:
            print(error_msg)
        return jsonify(error={"message": "An internal server error occurred retrieving control data."}), 500


# --- GET Endpoint (Retrieve Logs from PostgreSQL) ---
@control_api.get("/control/logsd") # Consider renaming to /control/logs
def get_control_logs():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        # Query logs using SQLAlchemy session
        log_entries = ControlActivityLogs.query.order_by(ControlActivityLogs.log_date.desc()).all()

        log_list = []
        for log_entry in log_entries:
            # --- Format timestamp using the helper function ---
            formatted_timestamp = format_datetime(log_entry.log_date)

            log_list.append({
                "log_id": log_entry.log_id,
                "timestamp": formatted_timestamp,  # Use formatted string from helper
                "pump1": log_entry.pump1,
                "pump2": log_entry.pump2,
                "exhaust": log_entry.exhaust,
                "automode": log_entry.automode,
                "logs_description": log_entry.logs_description
            })

        # Log successful retrieval
        if current_app:
            current_app.logger.info(f"Retrieved {len(log_list)} control log entries from database.")

        return jsonify(logs=log_list), 200 # Return logs under a 'logs' key

    except Exception as e:
         # Log the error
        error_msg = f"Error retrieving control logs from database: {e}"
        if current_app:
            current_app.logger.error(error_msg, exc_info=True)
        else:
            print(error_msg)
        # Use a more generic error message for the client
        return jsonify(error={"message": "An internal server error occurred retrieving logs."}), 500

# --- POST/PATCH Endpoints (Example Structure - Adapt as needed) ---
# You would need endpoints to actually *change* the control values in Firebase
# and then log those changes to PostgreSQL using log_control_change_db.

@control_api.patch("/control")
def update_control():
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

    data = request.get_json()
    if not data:
        return jsonify(error={"message": "No JSON data provided"}), 400

    try:
        ref = db.reference("pumpControl") # Or your control path

        # --- Validate incoming data ---
        allowed_fields = ["pump1", "pump2", "exhaust", "automode"]
        update_payload = {}
        log_payload = {} # Separate dict for logging clarity
        valid_data = False

        for field in allowed_fields:
            if field in data:
                value = data[field]
                # Add validation here (e.g., check if boolean, integer range)
                # Example basic validation: Check if boolean if expected
                if field in ["pump1", "pump2", "exhaust", "automode"]:
                    if not isinstance(value, bool):
                         return jsonify(error={"message": f"Invalid type for '{field}'. Expected boolean."}), 400

                update_payload[field] = value
                log_payload[field] = value # Add to log payload as well
                valid_data = True

        if not valid_data:
             return jsonify(error={"message": "No valid control fields provided for update."}), 400

        # --- Update Firebase ---
        ref.update(update_payload)
        if current_app:
            current_app.logger.info(f"Firebase control data updated: {update_payload}")

        # --- Log Change to PostgreSQL ---
        log_description = f"Control settings updated via API: {', '.join(update_payload.keys())}"
        log_control_change_db(
             pump1=log_payload.get("pump1"), # Use .get to handle missing keys gracefully
             pump2=log_payload.get("pump2"),
             exhaust=log_payload.get("exhaust"),
             automode=log_payload.get("automode"),
             description=log_description
        )

        return jsonify(message="Control settings updated successfully", updated_values=update_payload), 200

    except Exception as e:
        error_msg = f"Error updating control values: {e}"
        if current_app:
            current_app.logger.error(error_msg, exc_info=True)
        else:
            print(error_msg)
        return jsonify(error={"message": "An internal server error occurred during update."}), 500
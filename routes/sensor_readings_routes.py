# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\sensor_readings_routes.py
import os
from db import db
from flask import Blueprint, request, jsonify, current_app
import traceback  # For detailed error logging
import pytz # <--- Added pytz import
from datetime import datetime # <--- Added datetime import

# Import the necessary models (for the original endpoint)
from models.sensors_readings_model import SensorReading

# --- Firebase Imports ---
# Ensure firebase_admin is installed: pip install firebase-admin
import firebase_admin
from firebase_admin import credentials, db as firebase_db
from firebase_admin import exceptions as firebase_exceptions  # Import specific exceptions

# --- Blueprint Definition ---
sensor_readings_api = Blueprint("sensor_readings_api", __name__)

# --- Configuration ---
# Load API Key from environment variable - SET THIS
API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace")
PH_TZ = pytz.timezone('Asia/Manila') # <--- Define Philippines Timezone

# Define component_ids - REMOVED as component_id is removed from model/routes
# PH_COMPONENT_ID = os.environ.get("PH_COMPONENT_ID", "ph_sensor")
# TDS_COMPONENT_ID = os.environ.get("TDS_COMPONENT_ID", "tds_sensor")
# PLANT_ID = os.environ.get("PLANT_ID", "default_plant")

# --- Helper Functions ---

def check_api_key(request):
    """Checks if the provided API key in the header is valid."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        current_app.logger.warning(f"Unauthorized API attempt with key: {api_key_header}")
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403
    return None

def format_datetime_ph(dt):
    """Formats a datetime object to Philippines time (YYYY-MM-DD hh:mm:ss AM/PM)."""
    if not dt or not isinstance(dt, datetime):
        # Handle cases where dt might be None or not a datetime object
        return None
    try:
        # Assume naive datetime from DB represents UTC or needs localization
        # If your DB stores naive times that are ACTUALLY PH time, use localize directly.
        # If your DB stores aware times (TIMESTAMP WITH TIME ZONE), use astimezone.
        # Assuming DB stores naive UTC or server time that needs conversion:
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
             # Localize as UTC first, then convert
             dt_aware_utc = pytz.utc.localize(dt)
             dt_aware_ph = dt_aware_utc.astimezone(PH_TZ)
             # Alternatively, if naive IS PH time: dt_aware_ph = PH_TZ.localize(dt)
        else:
            # If already timezone-aware, convert to PH time
            dt_aware_ph = dt.astimezone(PH_TZ)

        # Format: YYYY-MM-DD HH:MM:SS AM/PM (12-hour clock, %I)
        return dt_aware_ph.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        current_app.logger.warning(f"Could not format datetime {dt} to PH time: {e}")
        # Fallback to ISO format or simple string
        return dt.isoformat()


# --- Original Route (fetches from PostgreSQL) ---
@sensor_readings_api.get("/sensor-readings")
def get_all_sensor_readings_db():
    """Fetches all sensor readings from the PostgreSQL database."""
    try:
        api_key_error = check_api_key(request)
        if api_key_error: return api_key_error

        # Query all sensor readings from DB, ordered by time descending
        query_data = SensorReading.query.order_by(SensorReading.reading_time.desc()).all()

        if not query_data:
            current_app.logger.info("No sensor readings found in the database.")
            return jsonify(db_readings=[]), 200 # Return 200 OK with empty list

        # Format the data for JSON response
        readings_list = [{
            "reading_id": data.reading_id,
            "reading_value": float(data.reading_value) if data.reading_value is not None else None,
            # Use the new formatting helper for PH time with AM/PM
            "reading_time": format_datetime_ph(data.reading_time), # <--- USE HELPER
            "unit": data.unit,
        } for data in query_data]

        current_app.logger.info(f"Fetched {len(readings_list)} readings from database.")
        return jsonify(db_readings=readings_list), 200  # Wrap in key

    except Exception as e:
        current_app.logger.error(f"Error fetching sensor readings from DB: {str(e)}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching DB readings."}), 500


# --- NEW Firebase Route ---
@sensor_readings_api.get("/sensor-readings/firebase")
def get_firebase_sensor_readings():
    """Fetches the latest pH and TDS sensor readings from Firebase Realtime Database."""
    try:
        api_key_error = check_api_key(request)
        if api_key_error: return api_key_error

        # --- CHECK FOR FIREBASE INITIALIZATION ERRORS ---
        if 'FIREBASE_INIT_ERROR' in current_app.config:
            error_message = current_app.config['FIREBASE_INIT_ERROR']
            traceback_message = current_app.config.get('FIREBASE_INIT_TRACEBACK', 'No traceback available')
            current_app.logger.error(f"Firebase initialization failed previously: {error_message}")
            return jsonify(error={
                "message": "Firebase service is unavailable due to initialization error.",
                "details": error_message,
                "traceback": traceback_message
            }), 503 # Service Unavailable

        # Check if Firebase SDK was initialized properly
        if not firebase_admin._apps:
            current_app.logger.error("Firebase Admin SDK is not initialized. Cannot fetch readings.")
            return jsonify(error={"message": "Firebase service is not properly initialized."}), 503

        # --- Fetch data from Firebase ---
        ph_data = None
        tds_data = None
        firebase_error = None

        # Get current PH time for timestamping Firebase reads if they lack one
        now_ph = datetime.now(PH_TZ)
        formatted_ph_timestamp = now_ph.strftime("%Y-%m-%d %I:%M:%S %p") # Format with AM/PM

        try:
            ref = firebase_db.reference('sensorReadings')

            # Fetch pH data
            ph_ref = ref.child('ph')
            ph_raw = ph_ref.get()
            if ph_raw is not None:
                # Extract value, assume timestamp is "now" in PH time
                ph_value = ph_raw.get("value") if isinstance(ph_raw, dict) else ph_raw
                ph_data = {
                    "value": ph_value,
                    "timestamp": formatted_ph_timestamp # Use formatted PH time
                }
                current_app.logger.debug(f"Fetched pH from Firebase: {ph_data}")
            else:
                current_app.logger.warning("No 'ph' data found at sensorReadings/ph in Firebase.")

            # Fetch TDS data
            tds_ref = ref.child('tds')
            tds_raw = tds_ref.get()
            if tds_raw is not None:
                # Extract value, assume timestamp is "now" in PH time
                tds_value = tds_raw.get("value") if isinstance(tds_raw, dict) else tds_raw
                tds_data = {
                    "value": tds_value,
                    "timestamp": formatted_ph_timestamp # Use formatted PH time
                }
                current_app.logger.debug(f"Fetched TDS from Firebase: {tds_data}")
            else:
                current_app.logger.warning("No 'tds' data found at sensorReadings/tds in Firebase.")

        except firebase_exceptions.FirebaseError as fb_err:
            firebase_error = f"Firebase specific error: {fb_err}"
            current_app.logger.error(firebase_error, exc_info=True)
        except Exception as e:
            firebase_error = f"Unexpected error during Firebase fetch: {e}"
            current_app.logger.error(firebase_error, exc_info=True)

        if firebase_error:
            # Return error if Firebase interaction failed
            return jsonify(error={"message": "Failed to fetch data from Firebase.", "details": firebase_error}), 500

        # --- Format Response ---
        response_data = {
            "ph": ph_data,
            "tds": tds_data
        }

        # Check if *any* data was found
        if ph_data is None and tds_data is None:
            current_app.logger.info("No pH or TDS data found in Firebase at specified paths.")
            return jsonify(message="No sensor readings found in Firebase.", firebase_readings=response_data), 404
        else:
            current_app.logger.info("Successfully fetched sensor readings from Firebase.")
            return jsonify(firebase_readings=response_data), 200

    except Exception as e:
        # Catch errors outside the Firebase fetch block
        current_app.logger.error(f"Error in /sensor-readings/firebase endpoint: {str(e)}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# --- New POST Route for Sensor Readings to DB ---
@sensor_readings_api.post("/sensor-readings")
def create_sensor_reading():
    """Creates a new sensor reading in the PostgreSQL database."""
    try:
        api_key_error = check_api_key(request)
        if api_key_error: return api_key_error

        # Get data from the request form
        reading_value_str = request.form.get("reading_value")
        unit = request.form.get("unit")

        # Validate the incoming data
        errors = {}
        if not request.form:
            current_app.logger.warning("No data provided in request form.")
            return jsonify(error={"message": "No data provided in the request form."}), 400

        if not reading_value_str: errors['reading_value'] = "Required field."
        if not unit: errors['unit'] = "Required field."

        # Attempt to convert reading_value to float
        reading_value = None
        if 'reading_value' not in errors:
            try:
                reading_value = float(reading_value_str)
            except (ValueError, TypeError):
                errors['reading_value'] = "Invalid reading_value. Must be a number."

        if errors:
            current_app.logger.warning(f"Validation errors in POST /sensor-readings: {errors}. Data: {request.form}")
            return jsonify(error={"message": "Validation failed.", "details": errors}), 400

        # Create a new SensorReading object
        # reading_time is set by DB default
        new_reading = SensorReading(
            reading_value=reading_value,
            unit=unit
        )

        # Add the new reading to the database
        db.session.add(new_reading)
        db.session.commit() # Commit to get the reading_id and reading_time

        current_app.logger.info(f"New sensor reading created with reading_id: {new_reading.reading_id}")

        # Return the new reading as a JSON response
        return jsonify(
            message="Sensor reading created successfully.",
            sensor_reading={
                "reading_id": new_reading.reading_id,
                "reading_value": float(new_reading.reading_value),
                # Format the timestamp from DB using the helper
                "reading_time": format_datetime_ph(new_reading.reading_time), # <--- USE HELPER
                "unit": new_reading.unit
            }
        ), 201

    except Exception as e:
        db.session.rollback() # Rollback in case of error
        current_app.logger.error(f"Error creating sensor reading: {str(e)}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while creating the sensor reading."}), 500


# --- Scheduled Task Function (Outside the Blueprint) ---
def fetch_and_store_firebase_data(app):
    """
    Fetches latest pH/TDS from Firebase and stores in PostgreSQL database.
    Designed to be run by a scheduler (e.g., APScheduler, Celery).
    """
    with app.app_context(): # Ensure access to app config, logger, db
        logger = current_app.logger # Get logger within context
        try:
            # API Key Check - Not needed for internal task, but good practice?
            # api_key = os.environ.get("API_KEY")
            # if not api_key:
            #     logger.error("API_KEY not set in environment variables. Scheduled task aborted.")
            #     return

            # --- CHECK FOR FIREBASE INITIALIZATION ERRORS ---
            if 'FIREBASE_INIT_ERROR' in current_app.config:
                error_message = current_app.config['FIREBASE_INIT_ERROR']
                logger.error(f"Firebase initialization failed previously: {error_message}")
                return # Stop task if Firebase init failed

            # Check if Firebase SDK was initialized
            if not firebase_admin._apps:
                logger.error("Firebase Admin SDK is not initialized. Scheduled task cannot fetch readings.")
                return

            # --- Fetch data from Firebase ---
            ph_data = None
            tds_data = None
            now_ph_for_logging = datetime.now(PH_TZ) # Get PH time for logging

            try:
                ref = firebase_db.reference('sensorReadings')

                # Fetch pH data
                ph_ref = ref.child('ph')
                ph_raw = ph_ref.get()
                if ph_raw is not None:
                    ph_value = ph_raw.get("value") if isinstance(ph_raw, dict) else ph_raw
                    ph_data = {"value": ph_value}
                    logger.debug(f"Fetched pH value from Firebase: {ph_value}")
                else:
                    logger.warning("Scheduled task: No 'ph' data found at sensorReadings/ph in Firebase.")

                # Fetch TDS data
                tds_ref = ref.child('tds')
                tds_raw = tds_ref.get()
                if tds_raw is not None:
                     tds_value = tds_raw.get("value") if isinstance(tds_raw, dict) else tds_raw
                     tds_data = {"value": tds_value}
                     logger.debug(f"Fetched TDS value from Firebase: {tds_value}")
                else:
                    logger.warning("Scheduled task: No 'tds' data found at sensorReadings/tds in Firebase.")

            except firebase_exceptions.FirebaseError as fb_err:
                logger.error(f"Scheduled task: Firebase specific error during fetch: {fb_err}", exc_info=True)
                return # Stop task on Firebase error
            except Exception as e:
                logger.error(f"Scheduled task: Unexpected error during Firebase fetch: {e}", exc_info=True)
                return # Stop task on other fetch error

            # --- Database Insertion ---
            db_session = db.session # Get the database session
            added_count = 0
            try:
                # Insert pH data if fetched
                if ph_data and ph_data.get("value") is not None:
                    # reading_time set by DB default
                    new_ph_reading = SensorReading(
                        reading_value=ph_data["value"],
                        unit="pH"
                    )
                    db_session.add(new_ph_reading)
                    added_count += 1
                    logger.info(f"Scheduled task: Storing pH reading {ph_data['value']} at {now_ph_for_logging.strftime('%Y-%m-%d %I:%M:%S %p')}")

                # Insert TDS data if fetched
                if tds_data and tds_data.get("value") is not None:
                    # reading_time set by DB default
                    new_tds_reading = SensorReading(
                        reading_value=tds_data["value"],
                        unit="ppm"
                    )
                    db_session.add(new_tds_reading)
                    added_count += 1
                    logger.info(f"Scheduled task: Storing TDS reading {tds_data['value']} at {now_ph_for_logging.strftime('%Y-%m-%d %I:%M:%S %p')}")

                if added_count > 0:
                     db_session.commit() # Commit the changes if anything was added
                     logger.info(f"Scheduled task: Successfully stored {added_count} Firebase reading(s) in the database.")
                else:
                     logger.info("Scheduled task: No new Firebase data to store in DB.")

            except Exception as e:
                db_session.rollback() # Rollback in case of DB error
                logger.error(f"Scheduled task: Error storing sensor readings in DB: {str(e)}", exc_info=True)
            # No finally block needed if using Flask-SQLAlchemy session management

        except Exception as e:
            # Catch outer errors (e.g., within app_context)
            logger.error(f"Outer exception in scheduled task 'fetch_and_store_firebase_data': {e}", exc_info=True)
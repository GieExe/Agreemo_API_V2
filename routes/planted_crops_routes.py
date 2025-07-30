# C:\Users\Giebert\PcharmProjects\agreemo_api_v2\routes\planted_crops_routes.py

import os
from flask import Blueprint, request, jsonify, current_app, Response # Ensure Response is imported
from db import db
from models.planted_crops_model import PlantedCrops
from models.greenhouses_model import Greenhouse
from models.users_model import Users # Make sure this path is correct
from models.activity_logs.planted_crop_activity_logs_model import PlantedCropActivityLogs
from datetime import datetime, date
import pytz
import psycopg2
import json
from sqlalchemy.exc import IntegrityError, DataError
from decimal import Decimal, InvalidOperation

# Define the Blueprint
planted_crops_api = Blueprint("planted_crops_api", __name__)

# Load API Key from environment variable
# Use environment variables in production for API_KEY
API_KEY = os.environ.get("API_KEY", "YOUR_DEFAULT_FALLBACK_API_KEY") # Replace default
PH_TZ = pytz.timezone('Asia/Manila') # Define timezone for logging if needed


# --- Notification Functions ---
def send_planted_crop_notification(payload):
    """Sends notification via PostgreSQL NOTIFY for planted crop changes."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error("Error: SQLALCHEMY_DATABASE_URI not configured for notifications.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
             # Ensure channel name is safe (basic validation)
            if not 'planted_crops_updates'.isalnum() and '_' not in 'planted_crops_updates':
                 current_app.logger.error(f"Invalid hardcoded channel name attempted: planted_crops_updates")
                 conn.close()
                 return
            # Use json.dumps with default=str for better type handling (dates, decimals)
            curs.execute(f"NOTIFY planted_crops_updates, %s;", (json.dumps(payload, default=str),))
        conn.close()
        current_app.logger.info(f"Sent notification to channel 'planted_crops_updates': {payload}")
    except psycopg2.Error as e:
        current_app.logger.error(f"Database error sending planted crop notification: {e}", exc_info=True)
        if 'conn' in locals() and conn: conn.close()
    except Exception as e:
        current_app.logger.error(f"Unexpected error in send_planted_crop_notification: {e}", exc_info=True)
        if 'conn' in locals() and conn: conn.close()


def send_planted_crop_logs_notification(payload):
    """Sends notification via PostgreSQL NOTIFY for planted crop log changes."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error("Error: SQLALCHEMY_DATABASE_URI not configured for notifications.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
             # Ensure channel name is safe (basic validation)
            if not 'planted_crops_logs_updates'.isalnum() and '_' not in 'planted_crops_logs_updates':
                 current_app.logger.error(f"Invalid hardcoded channel name attempted: planted_crops_logs_updates")
                 conn.close()
                 return
            curs.execute(f"NOTIFY planted_crops_logs_updates, %s;", (json.dumps(payload, default=str),))
        conn.close()
        current_app.logger.info(f"Sent notification to channel 'planted_crops_logs_updates': {payload}")
    except psycopg2.Error as e:
        current_app.logger.error(f"Database error sending planted crop log notification: {e}", exc_info=True)
        if 'conn' in locals() and conn: conn.close()
    except Exception as e:
        current_app.logger.error(f"Unexpected error in send_planted_crop_logs_notification: {e}", exc_info=True)
        if 'conn' in locals() and conn: conn.close()


# --- Helper Function for Logging ---
def log_planted_crop_activity(user_id, plant_id, description):
    """
    Creates and adds a PlantedCropActivityLogs entry to the session.
    Accepts user_id (can be None for API actions) which maps to login_id.
    Returns the log object on success, raises exception on failure.
    """
    # We need to handle the case where user_id=None for API-key based actions
    # BUT the foreign key constraint 'planted_crop_activity_logs_login_id_fkey'
    # likely requires login_id to reference users.user_id and might not allow NULL.
    # Let's assume a generic system user ID (e.g., 0) exists for API actions if user_id is None.
    SYSTEM_USER_ID_FOR_LOGS = 0 # Ensure this user exists in your 'users' table

    log_user_id = user_id if user_id is not None else SYSTEM_USER_ID_FOR_LOGS

    if log_user_id is None: # Double check if SYSTEM_USER_ID is also None somehow
        current_app.logger.error(f"Cannot log activity for plant_id {plant_id}: No valid user ID provided or configured for system actions.")
        raise ValueError("Cannot log activity without a valid user ID or system user ID.")

    try:
        # Use timezone-aware time
        log_time_aware = datetime.now(PH_TZ)

        new_log = PlantedCropActivityLogs(
            login_id=log_user_id, # Use resolved user ID
            plant_id=plant_id,
            logs_description=description,
            log_date=log_time_aware # Store timezone-aware time
        )
        db.session.add(new_log)
        db.session.flush() # Assigns log_id before commit

        # Send notification about the new log entry *after* successful flush
        send_planted_crop_logs_notification({
            "action": "insert",
            "log_id": new_log.log_id,
            "plant_id": plant_id,
            "description": description,
            "user_id": log_user_id # Report the ID used for logging
        })

        current_app.logger.info(f"Activity log added to session for plant_id {plant_id} by resolved user_id {log_user_id}: {description}")
        return new_log
    except IntegrityError as ie:
        # Log the error but allow the main transaction to potentially continue/rollback
        db.session.rollback() # Rollback log attempt immediately on IntegrityError
        current_app.logger.error(f"Database integrity error adding activity log to session for plant_id {plant_id} (User ID attempted: {log_user_id}): {ie}", exc_info=True)
        # Re-raise because logging is often crucial
        raise ie
    except Exception as e:
        # Log the error
        db.session.rollback() # Rollback log attempt
        current_app.logger.error(f"Unexpected error adding activity log to session for plant_id {plant_id} (User ID attempted: {log_user_id}): {e}", exc_info=True)
        # Re-raise
        raise e


# --- Helper Function for Calculating Days Since a Date ---
def calculate_days_since(start_date):
    """Calculates the number of days from start_date to today."""
    if not start_date: return 0
    today = date.today()
    # Ensure start_date is just a date object if it's datetime
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    try:
        delta = today - start_date
        return max(0, delta.days) # Ensure non-negative days
    except TypeError: # Handle potential comparison issues if types are wrong
        current_app.logger.warning(f"Could not calculate days since invalid date type: {type(start_date)}, value: {start_date}")
        return 0


# --- API Routes ---

@planted_crops_api.get("/planted_crops")
def get_all_planted_crops():
    """Retrieves all planted crops, calculating current ages dynamically."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403
    try:
        greenhouse_id_filter = request.args.get('greenhouse_id', type=int)
        query = PlantedCrops.query
        if greenhouse_id_filter:
            query = query.filter(PlantedCrops.greenhouse_id == greenhouse_id_filter)

        # Eager load greenhouse related data only if needed for other processing
        planted_crops_list = query.options(db.joinedload(PlantedCrops.greenhouses))\
                                   .order_by(PlantedCrops.planting_date.desc(), PlantedCrops.plant_id.desc()).all()

        if not planted_crops_list:
            message = "No planted crops found matching the criteria." if greenhouse_id_filter else "No planted crops found."
            return jsonify(message=message, count=0, planted_crops=[]), 200

        result_list = []
        today = date.today() # Get today's date once for efficiency
        for crop in planted_crops_list:
            # Calculate days spent IN the greenhouse since planting
            days_in_greenhouse = 0
            if crop.planting_date:
                 if isinstance(crop.planting_date, datetime):
                      planting_dt = crop.planting_date.date()
                 else:
                      planting_dt = crop.planting_date
                 try:
                      delta = today - planting_dt
                      days_in_greenhouse = max(0, delta.days)
                 except TypeError: pass # Keep 0 if date types are wrong

            # Calculate the ACTUAL total age (handling None for seedlings_daysOld)
            seedlings_age = crop.seedlings_daysOld if crop.seedlings_daysOld is not None else 0
            actual_total_days = seedlings_age + days_in_greenhouse

            result_list.append({
                "plant_id": crop.plant_id,
                "greenhouse_id": crop.greenhouse_id,
                # "greenhouse_name": crop.greenhouses.name if crop.greenhouses else "N/A", # REMOVED
                "plant_name": crop.plant_name, # Auto-generated name (e.g., P1-041525)
                "name": crop.name,         # User's full name who added the crop
                "planting_date": crop.planting_date.isoformat() if crop.planting_date else None,
                "seedlings_daysOld": crop.seedlings_daysOld,
                "greenhouse_daysOld": days_in_greenhouse, # Show days SINCE planting
                "count": crop.count,
                "tds_reading": float(crop.tds_reading) if crop.tds_reading is not None else None,
                "ph_reading": float(crop.ph_reading) if crop.ph_reading is not None else None,
                "status": crop.status,
                "total_days_grown": actual_total_days # Show the SUM dynamically calculated
            })
        return jsonify(message=f"Successfully retrieved {len(result_list)} planted crop(s).", count=len(result_list), planted_crops=result_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching planted crops: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


@planted_crops_api.get("/planted_crops/<int:plant_id>")
def get_planted_crop_by_id(plant_id):
    """Retrieves a specific planted crop, calculating current ages dynamically."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403
    try:
        # Eager load greenhouse only if needed elsewhere
        crop = db.session.query(PlantedCrops).options(db.joinedload(PlantedCrops.greenhouses)).get(plant_id)
        if not crop:
            return jsonify(error={"message": f"Planted crop with ID {plant_id} not found."}), 404

        # Calculate days spent IN the greenhouse since planting
        days_in_greenhouse = calculate_days_since(crop.planting_date)
        # Calculate the ACTUAL total age (handling None for seedlings_daysOld)
        seedlings_age = crop.seedlings_daysOld if crop.seedlings_daysOld is not None else 0
        actual_total_days = seedlings_age + days_in_greenhouse

        result_dict = {
            "plant_id": crop.plant_id,
            "greenhouse_id": crop.greenhouse_id,
            # "greenhouse_name": crop.greenhouses.name if crop.greenhouses else "N/A", # REMOVED
            "plant_name": crop.plant_name, # Auto-generated name
            "name": crop.name,         # User's full name
            "planting_date": crop.planting_date.isoformat() if crop.planting_date else None,
            "seedlings_daysOld": crop.seedlings_daysOld,
            "greenhouse_daysOld": days_in_greenhouse, # Show days SINCE planting
            "count": crop.count,
            "tds_reading": float(crop.tds_reading) if crop.tds_reading is not None else None,
            "ph_reading": float(crop.ph_reading) if crop.ph_reading is not None else None,
            "status": crop.status,
            "total_days_grown": actual_total_days # Show the SUM dynamically calculated
        }
        return jsonify(planted_crop=result_dict), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching planted crop {plant_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


@planted_crops_api.post("/planted_crops")
def add_planted_crop():
    """Adds a new planted crop using form data.
       Requires 'user_email' in form to find user, log activity, and set creator's 'name'.
       Auto-generates 'plant_name' as P<plant_id>-<MMDDYY>.
       Stores calculated initial 'total_days_grown' and 'greenhouse_daysOld'.
       Response calculates ages dynamically."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

    # --- Get data from form ---
    greenhouse_id_str = request.form.get("greenhouse_id")
    planting_date_str = request.form.get("planting_date") # YYYY-MM-DD
    seedlings_daysOld_str = request.form.get("seedlings_daysOld")
    count_str = request.form.get("count")
    email = request.form.get("user_email") # Email of the user adding the crop

    # Optional fields with defaults
    tds_reading_str = request.form.get("tds_reading", "650")
    ph_reading_str = request.form.get("ph_reading", "6.1")
    status = request.form.get("status", "not harvested")

    # --- Basic Validation ---
    required_fields_map = {
        "greenhouse_id": greenhouse_id_str, "planting_date": planting_date_str,
        "seedlings_daysOld": seedlings_daysOld_str, "count": count_str,
        "user_email": email
    }
    missing = [name for name, value in required_fields_map.items() if not value]
    if missing:
        return jsonify(error={"message": f"Missing required form fields: {', '.join(missing)}"}), 400

    try:
        # --- Find User ---
        user = Users.query.filter(Users.email.ilike(email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{email}' not found. Cannot add crop."}), 404
        if not user.isActive: # Check if user is active
             return jsonify(error={"message": f"User '{email}' is not active. Cannot add crop."}), 403
        user_full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip() or "Unknown User"

        # --- Data Conversions & Detailed Validation ---
        errors = {}
        greenhouse_id = None; planting_date_obj = None; seedlings_daysOld = None; count = None
        tds_reading_decimal = None; ph_reading_decimal = None; greenhouse = None

        try: greenhouse_id = int(greenhouse_id_str)
        except (ValueError, TypeError): errors['greenhouse_id'] = "Must be a valid integer."

        try: planting_date_obj = date.fromisoformat(planting_date_str)
        except (ValueError, TypeError): errors['planting_date'] = "Invalid date format. Use YYYY-MM-DD."

        try:
            seedlings_daysOld = int(seedlings_daysOld_str)
            if seedlings_daysOld < 0: errors['seedlings_daysOld'] = "Cannot be negative."
        except (ValueError, TypeError): errors['seedlings_daysOld'] = "Must be a valid integer."

        try:
            count = int(count_str)
            if count <= 0: errors['count'] = "Must be a positive integer."
        except (ValueError, TypeError): errors['count'] = "Must be a valid integer."

        try: tds_reading_decimal = Decimal(tds_reading_str) if tds_reading_str else Decimal("650")
        except InvalidOperation: errors['tds_reading'] = "Must be a valid number."

        try: ph_reading_decimal = Decimal(ph_reading_str) if ph_reading_str else Decimal("6.1")
        except InvalidOperation: errors['ph_reading'] = "Must be a valid number."

        # Validate Greenhouse Existence (only if ID is integer)
        if 'greenhouse_id' not in errors and greenhouse_id is not None:
            greenhouse = db.session.get(Greenhouse, greenhouse_id)
            if not greenhouse:
                 errors['greenhouse_id_invalid'] = f"Greenhouse with ID {greenhouse_id} not found."

        if errors:
            return jsonify(error={"message": "Validation failed.", "details": errors}), 400

        # --- Calculate initial values TO STORE ---
        # Ensure planting_date_obj is valid before calculation
        initial_days_in_greenhouse = 0
        if planting_date_obj:
             initial_days_in_greenhouse = calculate_days_since(planting_date_obj)

        # Ensure seedlings_daysOld is valid before calculation
        initial_total_age = 0
        if seedlings_daysOld is not None:
             initial_total_age = seedlings_daysOld + initial_days_in_greenhouse

        # --- Create Crop Instance ---
        new_crop = PlantedCrops(
            greenhouse_id=greenhouse.greenhouse_id,
            planting_date=planting_date_obj,
            name=user_full_name, # Creator's full name
            seedlings_daysOld=seedlings_daysOld,
            greenhouse_daysOld=initial_days_in_greenhouse, # Store initial days in GH
            count=count,
            tds_reading=tds_reading_decimal,
            ph_reading=ph_reading_decimal,
            status=status,
            total_days_grown=initial_total_age # Store calculated initial value
        )

        # --- Add, Flush, Generate plant_name ---
        db.session.add(new_crop)
        db.session.flush() # Assigns new_crop.plant_id

        generated_plant_name = ""
        try:
            if planting_date_obj:
                formatted_date = planting_date_obj.strftime("%m%d%y")
                generated_plant_name = f"P{new_crop.plant_id}-{formatted_date}"
                new_crop.plant_name = generated_plant_name
                current_app.logger.info(f"Generated plant_name: {generated_plant_name} for plant_id {new_crop.plant_id}")
            else:
                 raise ValueError("Planting date was invalid, cannot generate plant_name.")
        except Exception as name_gen_e:
             current_app.logger.error(f"Error generating plant_name for potential plant_id {new_crop.plant_id}: {name_gen_e}", exc_info=True)
             db.session.rollback() # Rollback if name generation fails
             return jsonify(error={"message": f"Failed to generate plant_name: {name_gen_e}"}), 500

        # --- Log Activity (using the found user's ID) ---
        try:
            log_description = (f"Plant '{new_crop.plant_name}' added by {user.email} "
                               f"to greenhouse '{greenhouse.name}' (ID: {greenhouse.greenhouse_id}).")
            log_planted_crop_activity(
                user_id=user.user_id, # Pass the actual user ID
                plant_id=new_crop.plant_id,
                description=log_description
            )
        except Exception as log_e:
             # If logging fails, we should rollback the plant addition too
             db.session.rollback()
             current_app.logger.error(f"Failed to log activity for plant add (ID tentatively {new_crop.plant_id}). Transaction rolled back. Error: {log_e}", exc_info=True)
             return jsonify(error={"message": f"Failed to create activity log. Plant not added. Log Error: {log_e}"}), 500


        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(f"Successfully committed Planted Crop ID: {new_crop.plant_id} "
                           f"({new_crop.plant_name}, created by '{new_crop.name}' - User ID: {user.user_id})")

        # --- Send Notification ---
        send_planted_crop_notification({
            "action": "insert", "plant_id": new_crop.plant_id,
            "greenhouse_id": new_crop.greenhouse_id, "plant_name": new_crop.plant_name,
            "name": new_crop.name # Include creator's name
        })

        # --- Prepare Response (Calculate dynamically for accuracy NOW) ---
        current_days_in_greenhouse = calculate_days_since(new_crop.planting_date)
        current_total_age = (new_crop.seedlings_daysOld if new_crop.seedlings_daysOld is not None else 0) + current_days_in_greenhouse

        response_data = {
             "plant_id": new_crop.plant_id, "greenhouse_id": new_crop.greenhouse_id,
             # "greenhouse_name": greenhouse.name, # REMOVED
             "plant_name": new_crop.plant_name, # Generated name
             "name": new_crop.name,           # Creator's full name
             "planting_date": new_crop.planting_date.isoformat() if new_crop.planting_date else None,
             "seedlings_daysOld": new_crop.seedlings_daysOld,
             "greenhouse_daysOld": current_days_in_greenhouse, # Calculated for response
             "count": new_crop.count,
             "tds_reading": float(new_crop.tds_reading) if new_crop.tds_reading is not None else None,
             "ph_reading": float(new_crop.ph_reading) if new_crop.ph_reading is not None else None,
             "status": new_crop.status,
             "total_days_grown": current_total_age # Calculated for response
        }
        return jsonify(message="Planted crop added successfully.", planted_crop=response_data), 201

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        error_msg = f"Database error: {error_detail}"
        status_code = 400
        current_app.logger.error(f"Database error adding planted crop: {e}", exc_info=True)
        if isinstance(e, IntegrityError):
            status_code = 409
            if 'violates unique constraint' in error_detail.lower() and 'plant_name' in error_detail.lower():
                 # Use generated_plant_name if available in this scope
                 name_in_error = generated_plant_name if 'generated_plant_name' in locals() else 'generated'
                 error_msg = f"Database error: Plant name '{name_in_error}' may already exist."
            elif 'violates not-null constraint' in error_detail.lower():
                 # Identify which column is null if possible from error_detail
                 col = 'required field'
                 if 'total_days_grown' in error_detail.lower(): col = 'total_days_grown'
                 elif 'greenhouse_daysOld' in error_detail.lower(): col = 'greenhouse_daysOld'
                 error_msg = f"Database error: '{col}' cannot be null."
            elif 'violates foreign key constraint' in error_detail.lower():
                if 'greenhouse_id' in error_detail.lower(): fk_field = 'greenhouse ID'
                else: fk_field = 'reference ID'
                error_msg = f"Database error: Invalid {fk_field} provided."
            else: error_msg = "Database error: Data integrity violation."
        elif isinstance(e, DataError): error_msg = f"Database error: Invalid data provided for a column type. Detail: {error_detail}"

        return jsonify(error={"message": error_msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error adding planted crop: {e}", exc_info=True)
        return jsonify(error={"message": "An unexpected server error occurred."}), 500


@planted_crops_api.put("/planted_crops/<int:plant_id>")
def update_planted_crop(plant_id):
    """Updates an existing planted crop using form data.
       Requires user 'email' in form for logging.
       'plant_name', creator 'name', CANNOT be updated directly.
       Calculated ages ('greenhouse_daysOld', 'total_days_grown') ARE updated
       automatically if 'planting_date' or 'seedlings_daysOld' changes.
    """
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

    email = request.form.get("email") # Email of the user performing the update
    if not email:
         return jsonify(error={"message": "Missing required form field: email (for logging)"}), 400

    try:
        # --- Find User performing the update (for logging) ---
        updater_user = Users.query.filter(Users.email.ilike(email)).first()
        if not updater_user:
            return jsonify(error={"message": f"User with email '{email}' not found. Cannot perform update."}), 404
        if not updater_user.isActive:
             return jsonify(error={"message": f"User '{email}' is not active. Cannot perform update."}), 403

        # --- Find Existing Crop (and potentially related greenhouse for logging) ---
        crop = db.session.query(PlantedCrops).options(db.joinedload(PlantedCrops.greenhouses)).get(plant_id)
        if not crop:
            return jsonify(error={"message": f"Planted crop with ID {plant_id} not found."}), 404

        # Store original values for comparison and logging
        original_values = {f.name: getattr(crop, f.name) for f in PlantedCrops.__table__.columns}

        # --- Update Fields selectively ---
        updated_fields = []
        validation_errors = {}
        recalculate_ages = False # Flag to update stored greenhouse_daysOld and total_days_grown

        # Log attempts to update non-modifiable fields
        ignored_updates = ["plant_name", "name", "greenhouse_daysOld", "total_days_grown"] # These are calculated or set on creation
        for field in ignored_updates:
            if field in request.form:
                 current_app.logger.warning(f"Attempt to update read-only/calculated field '{field}' for plant_id {plant_id} ignored.")

        # --- Process Allowed Updates ---
        # Using a loop for maintainability
        updatable_fields = {
            "planting_date": date.fromisoformat,
            "seedlings_daysOld": int,
            "count": int,
            "tds_reading": Decimal,
            "ph_reading": Decimal,
            "status": str
        }
        validation_rules = {
             "seedlings_daysOld": lambda x: x >= 0, # Must be non-negative
             "count": lambda x: x > 0, # Must be positive
             "status": lambda x: x in ["not harvested", "harvested"] # Example allowed statuses
        }
        field_log_names = list(updatable_fields.keys()) # Fields to check for changes

        for field, converter in updatable_fields.items():
            if field in request.form:
                value_str = request.form.get(field)
                current_value = getattr(crop, field)
                new_value = None
                try:
                    if value_str is None or value_str == '':
                         if field in ["tds_reading", "ph_reading"]: # Allow clearing optional numeric fields
                             new_value = None
                         else:
                              validation_errors[field] = "Cannot be empty if provided."
                              continue # Skip to next field
                    else:
                        new_value = converter(value_str)

                    # Check validation rules if any
                    if field in validation_rules and not validation_rules[field](new_value):
                         # Provide specific error based on rule
                         if field == "status": error_msg = f"Invalid status. Allowed: {', '.join(['not harvested', 'harvested'])}."
                         elif field == "seedlings_daysOld": error_msg = "Cannot be negative."
                         elif field == "count": error_msg = "Must be a positive integer."
                         else: error_msg = "Invalid value."
                         validation_errors[field] = error_msg
                         continue # Skip to next field

                    # Check if value actually changed (handle date/decimal comparison)
                    changed = False
                    if isinstance(new_value, Decimal) and current_value is not None:
                         changed = new_value != Decimal(current_value)
                    elif isinstance(new_value, date) and isinstance(current_value, date):
                        changed = new_value != current_value
                    elif new_value != current_value:
                        changed = True

                    if changed:
                         setattr(crop, field, new_value)
                         updated_fields.append(field)
                         if field in ["planting_date", "seedlings_daysOld"]:
                             recalculate_ages = True # Flag age recalculation

                except (ValueError, TypeError, InvalidOperation) as e:
                     validation_errors[field] = f"Invalid format or type: {e}"
                except Exception as e: # Catch unexpected errors during conversion/validation
                     validation_errors[field] = f"Error processing field: {e}"


        if validation_errors:
            return jsonify(error={"message": "Validation errors occurred during update.", "details": validation_errors}), 400

        # --- Recalculate and Update Stored ages if needed ---
        if recalculate_ages:
             current_days_in_greenhouse = calculate_days_since(crop.planting_date)
             seedling_age = crop.seedlings_daysOld if crop.seedlings_daysOld is not None else 0
             new_total_days = seedling_age + current_days_in_greenhouse

             if current_days_in_greenhouse != crop.greenhouse_daysOld:
                  crop.greenhouse_daysOld = current_days_in_greenhouse
                  # Don't log this implicit change unless desired
                  # if "greenhouse_daysOld" not in updated_fields: updated_fields.append("greenhouse_daysOld (recalculated)")

             if new_total_days != crop.total_days_grown:
                  crop.total_days_grown = new_total_days
                  # Log this implicit change as it affects a stored value
                  if "total_days_grown (recalculated)" not in updated_fields: updated_fields.append("total_days_grown (recalculated)")


        if not updated_fields:
            # Fetch and return current data if no *explicit* changes applied
            response_tuple = get_planted_crop_by_id(plant_id) # Reuse GET logic
            if isinstance(response_tuple, tuple) and len(response_tuple) > 0 and hasattr(response_tuple[0], 'json'):
                 status_code = response_tuple[1]
                 if status_code == 200:
                      return jsonify(message="No valid changes detected or applied.", planted_crop=response_tuple[0].json.get('planted_crop')), 200
            # Fallback if GET fails or structure is wrong
            return jsonify(message="No valid changes detected or applied."), 200


        # --- Log Update Activity (using updater's user ID) ---
        # Create more detailed log message comparing old/new values
        change_details = []
        for field in updated_fields:
             # Avoid logging potentially sensitive or very long fields directly
             if field in ["total_days_grown (recalculated)", "greenhouse_daysOld (recalculated)"]:
                  change_details.append(f"{field} updated")
             else:
                  old_val = original_values.get(field)
                  new_val = getattr(crop, field)
                  change_details.append(f"{field}: '{old_val}' -> '{new_val}'")

        log_description = (f"Plant '{crop.plant_name}' (ID: {plant_id}) updated by {updater_user.email}. "
                           f"Changes: {'; '.join(change_details)}.")
        try:
            log_planted_crop_activity(
                user_id=updater_user.user_id, # Log the ID of the user making the update
                plant_id=crop.plant_id,
                description=log_description
            )
        except Exception as log_e:
             # If logging fails, we should rollback the update too
             db.session.rollback()
             current_app.logger.error(f"Failed to log activity for plant update (ID: {plant_id}). Transaction rolled back. Error: {log_e}", exc_info=True)
             return jsonify(error={"message": f"Failed to create activity log. Update not saved. Log Error: {log_e}"}), 500


        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(f"Successfully updated Planted Crop ID: {plant_id} by User ID: {updater_user.user_id}. Fields explicitly changed: {updated_fields}")

        # --- Send Notification ---
        send_planted_crop_notification({
            "action": "update", "plant_id": crop.plant_id,
            "updated_fields": updated_fields # Send list of explicitly changed fields
        })

        # --- Prepare Response (Calculate dynamically for accuracy NOW) ---
        # Use the current state of the 'crop' object after commit/refresh implicitly done by commit
        current_days_in_greenhouse = calculate_days_since(crop.planting_date)
        current_total_age = (crop.seedlings_daysOld if crop.seedlings_daysOld is not None else 0) + current_days_in_greenhouse
        response_data = {
             "plant_id": crop.plant_id, "greenhouse_id": crop.greenhouse_id,
             # "greenhouse_name": crop.greenhouses.name if crop.greenhouses else "N/A", # REMOVED
             "plant_name": crop.plant_name, # Read-only generated name
             "name": crop.name,           # Read-only creator's name
             "planting_date": crop.planting_date.isoformat() if crop.planting_date else None,
             "seedlings_daysOld": crop.seedlings_daysOld,
             "greenhouse_daysOld": current_days_in_greenhouse, # Calculated for response
             "count": crop.count,
             "tds_reading": float(crop.tds_reading) if crop.tds_reading is not None else None,
             "ph_reading": float(crop.ph_reading) if crop.ph_reading is not None else None,
             "status": crop.status,
             "total_days_grown": current_total_age # Calculated for response
        }
        return jsonify(message=f"Planted crop {plant_id} updated successfully.", planted_crop=response_data), 200

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        error_msg = f"Database error: {error_detail}"
        status_code = 400
        current_app.logger.error(f"Database error updating plant {plant_id}: {e}", exc_info=True)
        if isinstance(e, IntegrityError): status_code = 409
        # Check specific constraints if needed
        elif 'violates not-null constraint' in error_detail.lower():
             col = 'required field'
             if 'total_days_grown' in error_detail.lower(): col = 'total_days_grown'
             elif 'greenhouse_daysOld' in error_detail.lower(): col = 'greenhouse_daysOld'
             error_msg = f"Database error: '{col}' became null during update (check calculation)."
        return jsonify(error={"message": error_msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error updating plant {plant_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An unexpected server error occurred."}), 500


@planted_crops_api.delete("/planted_crops/<int:plant_id>")
def delete_planted_crop(plant_id):
    """
    Deletes a specific planted crop and its associated logs.
    Requires a valid API key in the 'x-api-key' header.
    Logs the deletion action as performed via API Key authentication (uses generic system user ID).
    """
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

    try:
        # --- Find Existing Crop ---
        crop = db.session.query(PlantedCrops).options(db.joinedload(PlantedCrops.greenhouses)).get(plant_id)
        if not crop:
            return jsonify(error={"message": f"Planted crop with ID {plant_id} not found."}), 404

        # Store info before deletion for logging/notification
        greenhouse_id_ref = crop.greenhouse_id
        plant_name_ref = crop.plant_name # The P<id>-MMDDYY name
        creator_name_ref = crop.name # The creator's full name

        # --- Log Deletion Activity (as API action, using generic system ID) ---
        log_description = (f"Plant '{plant_name_ref}' (ID: {plant_id}, originally created by '{creator_name_ref}') "
                           f"deleted via API request (authenticated by API key).")
        try:
            log_planted_crop_activity(
                user_id=None, # Will be resolved to SYSTEM_USER_ID_FOR_LOGS by helper
                plant_id=plant_id,
                description=log_description
            )
        except Exception as log_e:
             # If logging fails, should we stop deletion? For now, log error and continue.
             db.session.rollback() # Rollback the log attempt
             current_app.logger.error(f"Failed to log activity for plant deletion (ID: {plant_id}). Deletion will proceed. Error: {log_e}", exc_info=True)
             # Decide if deletion should be stopped:
             # return jsonify(error={"message": f"Failed to create activity log. Deletion cancelled. Log Error: {log_e}"}), 500

        # --- Delete Associated Activity Logs Explicitly ---
        # Safer than relying purely on cascade for bulk operations or complex scenarios
        logs_deleted_count = db.session.query(PlantedCropActivityLogs).filter(PlantedCropActivityLogs.plant_id == plant_id).delete(synchronize_session=False)
        if logs_deleted_count > 0:
             current_app.logger.info(f"Queued deletion for {logs_deleted_count} activity log records for plant ID {plant_id}.")

        # --- Delete the Planted Crop ---
        # Cascade delete should handle relations like Harvests, Rejections IF CONFIGURED CORRECTLY
        # on those models' relationships back to PlantedCrops (e.g., ondelete='CASCADE' on the FK).
        # If not configured, deletion will fail here due to IntegrityError.
        db.session.delete(crop)
        current_app.logger.info(f"Queued deletion for Planted Crop ID: {plant_id}.")

        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(f"Successfully committed deletion of Planted Crop ID: {plant_id} "
                           f"(Plant Name: '{plant_name_ref}') via API Key.")

        # --- Send Notification ---
        send_planted_crop_notification({
            "action": "delete", "plant_id": plant_id, "greenhouse_id": greenhouse_id_ref
        })

        # --- Success Response ---
        return jsonify(message=(f"Planted crop {plant_id} ('{plant_name_ref}', created by '{creator_name_ref}') "
                                f"and associated logs deleted successfully via API request.")
                      ), 200

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"DB integrity error deleting plant {plant_id}: {e}", exc_info=True)
        error_detail = str(getattr(e, 'orig', e))
        # Try to provide more specific message based on constraint name if available in error_detail
        if 'harvests_plant_id_fkey' in error_detail.lower(): msg = "Cannot delete crop because it is referenced by Harvest records."
        elif 'reason_for_rejection_plant_id_fkey' in error_detail.lower(): msg = "Cannot delete crop because it is referenced by Rejection records."
        elif 'nutrient_controller_plant_id_fkey' in error_detail.lower(): msg = "Cannot delete crop because it is referenced by Nutrient Controller records."
        # Add other FK checks (e.g., Sales)
        else: msg = f"Cannot delete crop due to existing database references. Please delete dependent records first. Detail: {error_detail}"
        return jsonify(error={"message": msg}), 409 # Conflict

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error deleting plant {plant_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An unexpected server error occurred during deletion."}), 500


# <<< --- NEW: DELETE ALL PLANTED CROPS (NO CONFIRMATION - DANGEROUS) --- >>>
@planted_crops_api.delete("/planted_crops")
def delete_all_planted_crops_no_confirm():
    """
    Deletes ALL planted crop records and their associated logs WITHOUT confirmation.
    !!! WARNING: THIS IS A HIGHLY DESTRUCTIVE OPERATION. USE WITH EXTREME CAUTION !!!
    Requires API Key for authorization. No other input needed.
    """
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

    current_app.logger.critical("!!! EXTREME WARNING: Attempting UNCONFIRMED bulk deletion of ALL planted crops and logs via API Key !!!")

    try:
        # 1. Delete associated logs first for safety
        num_logs_deleted = db.session.query(PlantedCropActivityLogs).delete(synchronize_session=False)
        current_app.logger.info(f"Queued deletion of {num_logs_deleted} planted crop activity logs.")

        # 2. Delete all planted crop records
        # This will FAIL if other tables (Harvests, Rejections, etc.) still reference these crops
        # and the foreign keys are not configured with ON DELETE CASCADE or SET NULL.
        num_crops_deleted = db.session.query(PlantedCrops).delete(synchronize_session=False)
        current_app.logger.info(f"Queued deletion of {num_crops_deleted} planted crop records.")

        # 3. Commit the transaction
        db.session.commit()
        log_msg = f"COMMITTED bulk deletion of {num_crops_deleted} planted crop records and {num_logs_deleted} associated logs. Triggered via API Key (NO confirmation)."
        current_app.logger.critical(log_msg) # Log successful execution as critical

        # 4. Send summary notification
        try:
            send_planted_crop_notification({
                "action": "delete_all",
                "crops_deleted_count": num_crops_deleted,
                "logs_deleted_count": num_logs_deleted,
                "deleted_by": "System/API Key (No Confirmation)"
            })
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send delete_all notification for planted crops: {notify_e}", exc_info=True)

        return jsonify(
            message=f"Successfully deleted {num_crops_deleted} planted crop records and {num_logs_deleted} associated logs. This action was performed WITHOUT confirmation."
        ), 200

    except IntegrityError as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        current_app.logger.error(f"CRITICAL FAILURE: Integrity error during bulk planted crop deletion: {e}", exc_info=True)
        # Provide a more specific message based on common dependencies
        msg = f"Cannot delete all planted crops due to existing database references. Detail: {error_detail}"
        if 'harvests_plant_id_fkey' in error_detail.lower(): msg = "Cannot delete all planted crops because Harvest records reference them. Delete harvests first."
        elif 'reason_for_rejection_plant_id_fkey' in error_detail.lower(): msg = "Cannot delete all planted crops because Rejection records reference them. Delete rejections first."
        elif 'nutrient_controller_plant_id_fkey' in error_detail.lower(): msg = "Cannot delete all planted crops because Nutrient Controller records reference them. Delete/dissociate controller records first."
        # Add other potential FK constraints
        return jsonify(error={"message": msg}), 409 # Use 409 Conflict

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"CRITICAL FAILURE: Error during unconfirmed bulk deletion of planted crops: {e}", exc_info=True)
        return jsonify(error={"message": "An error occurred during bulk deletion."}), 500
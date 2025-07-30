# C:\Users\Giebert\PcharmProjects\agreemo_api_v2\routes\harvests_routes.py

import os
from flask import Blueprint, request, jsonify, current_app, Response # Added Response here
from db import db
from models.harvest_model import Harvest
from models.planted_crops_model import PlantedCrops
from models.greenhouses_model import Greenhouse
from models.users_model import Users
# --- Import the AdminUser model ---
from models.admin_user_model import AdminUser
# --- End Import ---
from models.activity_logs.harvest_activity_logs_model import HarvestActivityLogs
# Assuming these are correctly imported and functional from the other file
try:
    # Try importing assuming it's in the same directory or PYTHONPATH includes routes
    from routes.planted_crops_routes import log_planted_crop_activity
except ImportError:
    # Handle case where the import path might be different or needs adjustment
    # This is a placeholder - adjust the import path based on your project structure
    current_app.logger.warning("Could not directly import log_planted_crop_activity from routes.planted_crops_routes. Ensure correct path.")
    # Define a dummy function if needed for the code to run without errors,
    # but actual logging for planted crops won't work from here without the real function.
    def log_planted_crop_activity(user_id, plant_id, description):
       print(f"Dummy log_planted_crop_activity: User {user_id}, Plant {plant_id}, Desc: {description}")
       pass # Replace with actual import logic

from datetime import datetime, date
import pytz
import psycopg2 # For sending NOTIFY commands
import json
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy import func
from decimal import Decimal, InvalidOperation # Keep if needed elsewhere, though update uses float

# Define the Blueprint
harvests_api = Blueprint("harvests_api", __name__)

# Load API Key and Timezone
# IMPORTANT: For production, use environment variables or a secure config management system
API_KEY = os.environ.get("API_KEY", "YOUR_DEFAULT_FALLBACK_API_KEY") # Replace default
PH_TZ = pytz.timezone('Asia/Manila')

# Define allowed statuses for creation and update
ALLOWED_HARVEST_STATUSES = ["Not Sold", "Sold", "Processing", "Spoiled"] # Add other relevant statuses


# --- Helper Functions ---
def check_api_key(request):
    """Checks if the provided API key in the header is valid."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        current_app.logger.warning(f"Failed API Key attempt from IP: {request.remote_addr}")
        return jsonify(error={"Not Authorised": "Incorrect or missing api_key."}), 403
    return None

def format_price(p):
    """Safely formats a price (Decimal/float) to float for JSON, handles None."""
    if p is None:
        return None
    try:
        # Ensure it's treated as float for consistency in JSON
        return float(p)
    except (ValueError, TypeError):
        current_app.logger.warning(f"Could not format price value {p} as float.")
        return None # Or return 0.0, or raise error depending on requirements

# *** CORRECTED format_datetime function ***
def format_datetime(dt):
    """
    Formats datetime or date objects to Philippines Time string (YYYY-MM-DD HH:MM:SS AM/PM)
    or just YYYY-MM-DD for date objects.
    """
    if dt is None:
        return None

    try:
        if isinstance(dt, datetime):
            # Ensure datetime is timezone-aware (assume UTC if naive, like from DB)
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                # If naive, assume it's UTC from the database
                dt_aware = pytz.utc.localize(dt)
            else:
                # If already aware, ensure it's in UTC before converting to PH
                dt_aware = dt.astimezone(pytz.utc)

            # Convert to Philippines Timezone
            dt_ph = dt_aware.astimezone(PH_TZ)
            # Format as YYYY-MM-DD HH:MM:SS AM/PM
            return dt_ph.strftime("%Y-%m-%d %I:%M:%S %p")
        elif isinstance(dt, date):
            # For date objects, just format as YYYY-MM-DD
            return dt.strftime("%Y-%m-%d")
        else:
            # Fallback for unexpected types
            current_app.logger.warning(f"format_datetime received unexpected type: {type(dt)}, value: {dt}")
            return str(dt)
    except Exception as e:
        current_app.logger.error(f"Error formatting date/datetime {dt}: {e}", exc_info=True)
        return str(dt) # Fallback on error

def send_notification(channel, payload):
    """Sends a notification payload to a specified PostgreSQL NOTIFY channel."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error(f"Database URI not configured. Cannot send notification to channel '{channel}'.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
            # Ensure payload is serializable to JSON, using default=str for robustness
            json_payload = json.dumps(payload, default=str)
             # Ensure channel name is safe (basic validation)
            if not channel.isalnum() and '_' not in channel:
                 current_app.logger.error(f"Invalid channel name attempted: {channel}")
                 conn.close() # Close connection before returning
                 return
            curs.execute(f"NOTIFY {channel}, %s;", (json_payload,))
        conn.close()
        current_app.logger.info(f"Sent notification to channel '{channel}'. Payload: {json_payload}")
    except psycopg2.Error as db_err:
        current_app.logger.error(f"Database error sending notification to channel '{channel}': {db_err}", exc_info=True)
        if 'conn' in locals() and conn: conn.close() # Ensure connection is closed on error
    except TypeError as json_err:
         current_app.logger.error(f"JSON serialization error for notification payload to channel '{channel}': {json_err}. Payload: {payload}", exc_info=True)
         if 'conn' in locals() and conn: conn.close() # Ensure connection is closed on error
    except Exception as e:
        current_app.logger.error(f"Unexpected error sending notification to channel '{channel}': {e}", exc_info=True)
        if 'conn' in locals() and conn: conn.close() # Ensure connection is closed on error


def log_harvest_activity(user_id_to_log, harvest_id, description):
    """Creates and adds a harvest activity log (linked to users.user_id), sends notification."""
    if user_id_to_log is None:
        current_app.logger.error(f"Attempted to log HarvestActivityLog with NULL user_id_to_log for harvest {harvest_id}. Description: {description}")
        return None # Indicate failure

    try:
        # Use timezone-aware timestamp for logging
        log_time_aware = datetime.now(PH_TZ) # Store log time in local PH time
        # Or use UTC: log_time_aware = datetime.now(pytz.utc)

        new_log = HarvestActivityLogs(
            login_id=user_id_to_log, # Ensure this column links to users.user_id
            harvest_id=harvest_id,
            logs_description=description,
            log_date=log_time_aware # Use the timezone-aware time
        )
        db.session.add(new_log)
        db.session.flush() # Assigns log_id

        # Use the corrected format_datetime for the notification payload
        notification_payload = {
            "action": "insert",
            "log_id": new_log.log_id,
            "harvest_id": harvest_id,
            "description": description,
            "user_id": user_id_to_log,
            "log_timestamp": format_datetime(log_time_aware) # Use the helper for consistent formatting
        }
        send_notification('harvests_logs_updates', notification_payload)

        current_app.logger.info(f"Prepared HarvestActivityLog ID {new_log.log_id} for harvest {harvest_id}, logged against user ID {user_id_to_log}.")
        return new_log # Return the log object on success
    except IntegrityError as ie:
         db.session.rollback()
         # Check if the error is due to a non-existent user_id
         if 'harvest_activity_logs_login_id_fkey' in str(ie) or \
            ('foreign key constraint' in str(ie).lower() and 'login_id' in str(ie).lower()):
             current_app.logger.error(f"CRITICAL: Foreign key violation (harvest_activity_logs_login_id_fkey) trying to log activity for harvest {harvest_id}. The user ID '{user_id_to_log}' provided does NOT exist in the 'users' table. Description: '{description}'", exc_info=True)
         else:
             # Log other integrity errors
             current_app.logger.error(f"Database integrity error preparing activity log for harvest {harvest_id} (User ID: {user_id_to_log}): {ie}", exc_info=True)
         return None # Indicate logging failed
    except Exception as e:
        db.session.rollback() # Rollback on any other error during logging
        current_app.logger.error(f"Unexpected error preparing activity log for harvest {harvest_id} (User ID: {user_id_to_log}): {e}", exc_info=True)
        return None # Indicate logging failed


# --- API Routes ---

# --- POST /harvests (Regular User Action) ---
@harvests_api.post("/harvests")
def add_harvest():
    """
    Adds a new harvest record using form data. Calculates total_price.
    Requires user_email, plant_id, details. Fetches plant_name from PlantedCrops.
    Updates the associated PlantedCrop status to 'harvested'.
    Accepts an optional 'status' field from the form, defaulting to 'Not Sold'.
    Performed by regular users identified by user_email.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # --- Get form data ---
    user_email = request.form.get("user_email")
    greenhouse_id_str = request.form.get("greenhouse_id")
    plant_id_str = request.form.get("plant_id")
    name = request.form.get("name") # Name for the harvest batch itself
    plant_type = request.form.get("plant_type")
    total_yield_str = request.form.get("total_yield")
    accepted_str = request.form.get("accepted")
    total_rejected_str = request.form.get("total_rejected")
    price_str = request.form.get("price")
    harvest_date_str = request.form.get("harvest_date") # Optional
    notes = request.form.get("notes") # Optional
    # --- Get optional status from form ---
    status_from_form = request.form.get("status")
    # --- End Get Status ---

    # --- Basic Required Field Validation ---
    required_fields = {
        "user_email": user_email, "greenhouse_id": greenhouse_id_str, "plant_id": plant_id_str,
        "name": name, "plant_type": plant_type, "total_yield": total_yield_str,
        "accepted": accepted_str, "total_rejected": total_rejected_str, "price": price_str
        # status is optional, harvest_date defaults
    }
    missing = [field for field, value in required_fields.items() if not value]
    if missing:
        return jsonify(error={"message": f"Missing required fields: {', '.join(missing)}"}), 400

    # --- Detailed Validation and Conversion ---
    errors = {}
    user = None; greenhouse = None; planted_crop = None; price_float = None;
    greenhouse_id = None; plant_id = None; total_yield = None; accepted = None; total_rejected = None;
    harvest_date_obj = None; plant_name_from_crop = None; calculated_total_price = None
    final_status = 'Not Sold' # Default status

    try:
        # Validate User
        user = Users.query.filter(Users.email.ilike(user_email)).first()
        if not user:
            errors['user_email'] = f"User with email '{user_email}' not found."
        elif not user.isActive:
             errors['user_status'] = f"User '{user_email}' is not active."

        # --- Validate Status (if provided) ---
        if status_from_form and status_from_form.strip():
            # Use strip() to handle potential whitespace
            provided_status = status_from_form.strip()
            if provided_status not in ALLOWED_HARVEST_STATUSES:
                errors['status'] = f"Invalid status '{provided_status}'. Allowed statuses: {', '.join(ALLOWED_HARVEST_STATUSES)}."
            else:
                final_status = provided_status # Use the validated status from the form
        # If status_from_form is None or empty, final_status remains 'Not Sold' (the default)
        # --- End Validate Status ---

        # Validate IDs and Numeric Fields
        try:
            greenhouse_id = int(greenhouse_id_str)
            plant_id = int(plant_id_str)
            total_yield = int(total_yield_str)
            accepted = int(accepted_str)
            total_rejected = int(total_rejected_str)

            if total_yield < 0 or accepted < 0 or total_rejected < 0:
                errors['yields_negative'] = "Yield values cannot be negative."
            # Ensure consistency between yield components
            elif total_yield != (accepted + total_rejected):
                errors['yield_consistency'] = f"Total yield ({total_yield}) must equal Accepted ({accepted}) + Rejected ({total_rejected})."

        except (ValueError, TypeError):
            errors['numeric_conversion'] = "Greenhouse ID, Plant ID, and Yield values must be valid integers."

        # Validate Price
        try:
            price_float = float(price_str)
            if price_float < 0:
                errors['price_negative'] = "Price cannot be negative."
        except (ValueError, TypeError):
            errors['price_invalid'] = "Price must be a valid number."

        # Validate Date
        if harvest_date_str:
            try:
                # Parse just the date part
                harvest_date_obj = date.fromisoformat(harvest_date_str)
            except ValueError:
                errors['harvest_date_format'] = "Invalid date format. Use YYYY-MM-DD."
        else:
            # Default to today's date in the correct timezone
            harvest_date_obj = datetime.now(PH_TZ).date()

        # --- FK and Logic Checks ---
        if not errors: # Proceed only if basic validations passed
            greenhouse = db.session.get(Greenhouse, greenhouse_id)
            if not greenhouse:
                errors['greenhouse_id_invalid'] = f"Greenhouse ID {greenhouse_id} not found."

            planted_crop = db.session.get(PlantedCrops, plant_id)
            if not planted_crop:
                errors['plant_id_invalid'] = f"Planted Crop ID {plant_id} not found."
            else:
                # Fetch plant_name from the source planted_crop record
                plant_name_from_crop = planted_crop.plant_name
                # Check if the plant actually belongs to the specified greenhouse
                if greenhouse and planted_crop.greenhouse_id != greenhouse_id:
                    errors['plant_greenhouse_mismatch'] = f"Plant {plant_id} ('{plant_name_from_crop}') belongs to Greenhouse {planted_crop.greenhouse_id}, not Greenhouse {greenhouse_id}."
                # Check if the plant is already marked as harvested
                if planted_crop.status == "harvested":
                    # Allow re-harvesting? Or should this be an error? Currently an error.
                    # Consider business logic: Maybe allow if status is different? Or never allow?
                    errors['plant_already_harvested'] = f"Planted Crop {plant_id} ('{plant_name_from_crop}') is already marked as harvested."
                    # If re-harvesting *is* allowed under certain conditions, modify this logic.

        # --- Calculate Total Price ---
        # Ensure prerequisite validations passed before calculation
        if 'price_negative' not in errors and 'price_invalid' not in errors and \
           'numeric_conversion' not in errors and 'yields_negative' not in errors and \
           accepted is not None and price_float is not None:
            try:
                # Perform calculation using float for simplicity, round the result
                calculated_total_price = round(float(price_float) * float(accepted), 2)
            except Exception as calc_err:
                 errors['total_price_calculation'] = f"Could not calculate total price: {calc_err}"
                 current_app.logger.error(f"Error calculating total_price: Price={price_float}, Accepted={accepted}. Error: {calc_err}")

        # --- Final Error Check Before DB Operations ---
        if errors:
            return jsonify(error={"message": "Validation failed.", "details": errors}), 400

        # --- Create Harvest Object ---
        new_harvest = Harvest(
            user_id=user.user_id, # ID of the user performing the action
            greenhouse_id=greenhouse_id,
            plant_id=plant_id,
            plant_name=plant_name_from_crop, # Store the name from the source plant
            name=name, # Name of this specific harvest batch
            plant_type=plant_type,
            total_yield=total_yield,
            accepted=accepted,
            total_rejected=total_rejected,
            price=price_float, # Store the validated price
            total_price=calculated_total_price, # Store the calculated total
            harvest_date=harvest_date_obj, # Store the date object
            notes=notes, # Optional notes
            # --- Set Status Explicitly ---
            status=final_status, # Use the validated or default status
            # --- End Set Status ---
            # last_updated is handled by default/onupdate in the model
        )

        # --- Update Plant Status ---
        # Store original status for logging
        original_plant_status = planted_crop.status
        planted_crop.status = "harvested" # Update the associated plant's status

        # --- Add Objects to Session ---
        db.session.add(new_harvest)
        db.session.add(planted_crop) # Add the updated plant crop object as well
        db.session.flush() # Get IDs (like new_harvest.harvest_id), check constraints early

        # --- Log Activities ---
        # Log harvest creation
        log_harvest_desc = (f"Harvest '{name}' (Plant: '{plant_name_from_crop}' ID:{plant_id}) recorded by user {user.email} (ID: {user.user_id}). "
                            f"Yield: T={total_yield}, A={accepted}, R={total_rejected}. Price: {price_float:.2f}. Total Price: {calculated_total_price:.2f}. Status set to: {final_status}.")
        harvest_log = log_harvest_activity(user.user_id, new_harvest.harvest_id, log_harvest_desc)
        # CRITICAL: Check if logging failed, rollback if so
        if not harvest_log:
             db.session.rollback()
             current_app.logger.error(f"Failed to log harvest activity for harvest add (Plant ID {plant_id}). Transaction rolled back.")
             # Return error, indicating logging failure prevented the operation
             return jsonify(error={"message": "Failed to create activity log. Harvest not added."}), 500

        # Log plant status change
        log_plant_desc = (f"Status changed from '{original_plant_status}' to 'harvested' by user {user.email} (ID: {user.user_id}) "
                          f"due to creation of Harvest ID {new_harvest.harvest_id} ('{name}').")
        # Ensure log_planted_crop_activity handles its own DB session/commit/errors appropriately
        log_planted_crop_activity(user.user_id, plant_id, log_plant_desc)

        # --- Commit Transaction ---
        db.session.commit()
        # Refresh to get DB-generated timestamps etc. if needed for response
        db.session.refresh(new_harvest)
        current_app.logger.info(f"Harvest {new_harvest.harvest_id} added by user {user.email}. Plant {plant_id} status updated to harvested. Harvest Status: {new_harvest.status}. Last Updated: {new_harvest.last_updated}")

        # --- Notifications ---
        # Notify about the new harvest
        send_notification('harvests_updates', {
            "action": "insert",
            "harvest_id": new_harvest.harvest_id,
            "plant_id": plant_id,
            "plant_name": plant_name_from_crop,
            "gh_id": greenhouse_id,
            "user_id": user.user_id,
            "name": name,
            "accepted_yield": accepted,
            "price": format_price(price_float),
            "total_price": format_price(calculated_total_price),
            "status": new_harvest.status, # Include final status
            "last_updated": format_datetime(new_harvest.last_updated) # Use corrected helper
        })
        # Notify about the plant status update
        send_notification('planted_crops_updates', {
            "action": "update",
            "plant_id": plant_id,
            "updated_fields": ["status"],
            "new_status": "harvested",
            "triggered_by": f"harvest_id:{new_harvest.harvest_id}"
        })

        # --- Success Response ---
        # Return key details including the actual status set
        return jsonify(
            message="Harvest recorded successfully. Plant status updated to harvested.",
            harvest_id=new_harvest.harvest_id,
            plant_id=plant_id,
            plant_name=plant_name_from_crop,
            price=format_price(price_float),
            total_price=format_price(calculated_total_price),
            status=new_harvest.status, # Return the actual status set
            last_updated=format_datetime(new_harvest.last_updated) # Use corrected helper
        ), 201

    # --- Error Handling ---
    except (IntegrityError, DataError) as e:
        db.session.rollback() # Always rollback on database errors
        error_detail = str(getattr(e, 'orig', str(e))) # Get specific DB error message
        status_code = 400 # Default bad request
        error_type = "Database Data Error"
        if isinstance(e, IntegrityError):
             status_code = 409 # Conflict for integrity issues
             error_type = "Database Constraint Violation"
             # Provide more specific messages based on common constraints
             if 'violates not-null constraint' in error_detail.lower() and 'status' in error_detail.lower():
                  msg = "Database error: 'status' cannot be null. Please ensure a default or provide a valid status."
             elif 'violates foreign key constraint' in error_detail.lower():
                  msg = f"Database error: Invalid reference ID provided (user, greenhouse, or plant). Details: {error_detail}"
             else: msg = f"{error_type}: {error_detail}" # Generic integrity error
        else: # DataError
             msg = f"{error_type}: Invalid data format or type. Details: {error_detail}"

        current_app.logger.error(f"{error_type} during POST /harvests: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback() # Rollback on unexpected errors
        status_code = 500 # Internal Server Error
        msg = "An unexpected internal server error occurred while adding the harvest."
        current_app.logger.error(f"Unexpected error during POST /harvests: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code


# --- GET /harvests (Read All or Filtered) ---
@harvests_api.get("/harvests")
def get_all_harvests():
    """
    Retrieves a list of harvest records. Supports filtering by greenhouse_id and plant_id.
    Includes related plant name, original planting date, price, total_price, status,
    last_updated timestamp (formatted to PH time).
    The 'name' field in the response represents the name of the user who recorded the harvest.
    Does NOT include greenhouse_name.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        gh_id_filter = request.args.get('greenhouse_id', type=int)
        plant_id_filter = request.args.get('plant_id', type=int)

        # Query Harvest, join with Users (for harvester name)
        query = db.session.query(
            Harvest,
            Users.first_name,
            Users.last_name
        ).select_from(Harvest).outerjoin(
            Users, Harvest.user_id == Users.user_id # Join Harvest with Users
        ).options(
            # Eager load related PlantedCrops for planting date fallback
            db.joinedload(Harvest.planted_crops)
        )

        # Apply filters
        if gh_id_filter:
            query = query.filter(Harvest.greenhouse_id == gh_id_filter)
        if plant_id_filter:
            query = query.filter(Harvest.plant_id == plant_id_filter)

        # Execute query, order results
        harvest_results = query.order_by(
            Harvest.harvest_date.desc(),
            Harvest.last_updated.desc(),
            Harvest.harvest_id.desc()
        ).all()

        status_code = 200
        count = len(harvest_results)
        message = f"Successfully retrieved {count} harvest(s)."
        if count == 0:
            message = "No harvests found matching the specified criteria." if (gh_id_filter or plant_id_filter) else "No harvests found in the system."

        result_list = []
        for h, user_first_name, user_last_name in harvest_results:
            # Get related data, handling potential None values
            plant_planting_date = h.planted_crops.planting_date if h.planted_crops else None
            plant_name = h.plant_name
            # Fallback if plant_name wasn't stored on the harvest record itself
            if not plant_name and h.planted_crops:
                plant_name = h.planted_crops.plant_name

            # Construct harvester name safely
            harvester_name_val = f"{user_first_name or ''} {user_last_name or ''}".strip()
            if not harvester_name_val: harvester_name_val = "Unknown User" # Handle case where user might be deleted or null

            result_list.append({
                "harvest_id": h.harvest_id,
                "user_id": h.user_id,
                # "harvester_name": harvester_name_val, # REMOVED this field as per desired output
                "greenhouse_id": h.greenhouse_id,
                # "greenhouse_name": gh_name, # REMOVED
                "plant_id": h.plant_id,
                "plant_name": plant_name,
                "planted_crop_planting_date": format_datetime(plant_planting_date),
                # *** Assign harvester_name_val to the 'name' key ***
                "name": harvester_name_val, # Represents the harvester's name now
                # *** END CHANGE ***
                "plant_type": h.plant_type,
                "total_yield": h.total_yield,
                "accepted": h.accepted,
                "total_rejected": h.total_rejected,
                "price": format_price(h.price),
                "total_price": format_price(h.total_price),
                "harvest_date": format_datetime(h.harvest_date),
                "notes": h.notes,
                "status": h.status,
                "last_updated": format_datetime(h.last_updated)
             })

        current_app.logger.info(f"GET /harvests request successful. Filters: GH={gh_id_filter}, Plant={plant_id_filter}. Count: {count}")
        return jsonify(message=message, count=count, harvests=result_list), status_code

    except Exception as e:
        current_app.logger.error(f"Error during GET /harvests: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching harvests."}), 500


# --- GET /harvests/<id> (Read Specific) ---
@harvests_api.get("/harvests/<int:harvest_id>")
def get_harvest_by_id(harvest_id):
    """
    Retrieves a specific harvest record by its ID.
    Includes related plant name, original planting date, price, total_price, status,
    last_updated timestamp (formatted to PH time).
    The 'name' field in the response represents the name of the user who recorded the harvest.
    Does NOT include greenhouse_name.
    Returns tuple: (jsonify(data), status_code)
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        # Query Harvest, join with Users, load PlantedCrops
        result = db.session.query(
            Harvest,
            Users.first_name,
            Users.last_name
        ).select_from(Harvest).outerjoin(
            Users, Harvest.user_id == Users.user_id # Join Harvest with Users
        ).options(
            db.joinedload(Harvest.planted_crops) # Eager load plant for planting date
        ).filter(Harvest.harvest_id == harvest_id).first()


        if not result:
            current_app.logger.info(f"Harvest ID {harvest_id} not found.")
            return jsonify(message=f"Harvest with ID {harvest_id} not found."), 404

        harvest, user_first_name, user_last_name = result

        # Get related data safely
        plant_planting_date = harvest.planted_crops.planting_date if harvest.planted_crops else None
        plant_name = harvest.plant_name
        if not plant_name and harvest.planted_crops: # Fallback
             plant_name = harvest.planted_crops.plant_name

        # Construct harvester name safely
        harvester_name_val = f"{user_first_name or ''} {user_last_name or ''}".strip()
        if not harvester_name_val: harvester_name_val = "Unknown User"

        # Build the result dictionary
        result_dict = {
            "harvest_id": harvest.harvest_id,
            "user_id": harvest.user_id,
            # "harvester_name": harvester_name_val, # REMOVED this field as per desired output
            "greenhouse_id": harvest.greenhouse_id,
            # "greenhouse_name": gh_name, # REMOVED
            "plant_id": harvest.plant_id,
            "plant_name": plant_name,
            "planted_crop_planting_date": format_datetime(plant_planting_date),
            # *** Assign harvester_name_val to the 'name' key ***
            "name": harvester_name_val, # Represents the harvester's name now
            # *** END CHANGE ***
            "plant_type": harvest.plant_type,
            "total_yield": harvest.total_yield,
            "accepted": harvest.accepted,
            "total_rejected": harvest.total_rejected,
            "price": format_price(harvest.price),
            "total_price": format_price(harvest.total_price),
            "harvest_date": format_datetime(harvest.harvest_date),
            "notes": harvest.notes,
            "status": harvest.status,
            "last_updated": format_datetime(harvest.last_updated)
        }
        current_app.logger.info(f"Successfully fetched Harvest ID {harvest_id}.")
        return jsonify(harvest=result_dict), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching harvest ID {harvest_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching the harvest."}), 500


# ===================================================
# === MODIFIED UPDATE HARVEST PRICE (ADMIN ONLY) ===
# ===================================================
@harvests_api.patch("/harvests/<int:harvest_id>")
def update_harvest_price(harvest_id): # Renamed for clarity
    """
    ADMIN ONLY: Updates ONLY the price of a harvest record using form data.
    Recalculates total_price based on the new price and existing accepted quantity.
    Requires admin_email in form data for AUTHORIZATION.
    Updates the 'last_updated' timestamp. Logs the action.
    Ignores other fields like status, notes, yields etc.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    admin_email = request.form.get("admin_email")
    if not admin_email:
        return jsonify(error={"message": "Admin email ('admin_email') is required for authorization."}), 400

    try:
        # --- AUTHORIZATION ---
        admin_user = AdminUser.query.filter(AdminUser.email.ilike(admin_email)).first()
        if not admin_user:
            current_app.logger.warning(f"Unauthorized PATCH price attempt on Harvest {harvest_id} by non-admin: {admin_email}")
            return jsonify(error={"message": "Access Denied. Admin privileges required."}), 403
        if admin_user.is_disabled:
             current_app.logger.warning(f"Disabled admin {admin_email} attempted PATCH price on Harvest {harvest_id}.")
             return jsonify(error={"message": "Access Denied. Administrator account is disabled."}), 403

        # --- Get Harvest (No need to load greenhouse here) ---
        # Use db.session.get for direct primary key lookup
        harvest = db.session.get(Harvest, harvest_id)
        # Note: joinedload for planted_crops is removed as it's not used in this function
        # If needed for some logic, add it back: .options(db.joinedload(Harvest.planted_crops))

        if not harvest:
            return jsonify(message=f"Harvest ID {harvest_id} not found."), 404

        # Check for missing original user ID (important for logging)
        if harvest.user_id is None:
             current_app.logger.error(f"CRITICAL: Harvest {harvest_id} is missing original user_id required for activity logging.")
             # Return 500 as this indicates a data integrity issue
             return jsonify(error={"message": f"Internal data error: Harvest {harvest_id} missing original user ID."}), 500

        # --- Process Price Update ---
        updated_fields_log = []
        validation_errors = {}
        price_changed = False
        update_occurred = False # Flag to track if any change was actually made

        # Store original values for comparison and logging
        original_price_float = float(harvest.price) if harvest.price is not None else None
        original_total_price_float = float(harvest.total_price) if harvest.total_price is not None else None

        # Log ignored fields attempt
        ignored_fields = [field for field in request.form if field not in ["admin_email", "price"]]
        if ignored_fields:
            current_app.logger.warning(f"Admin {admin_email} attempted to update ignored fields via price update endpoint for Harvest {harvest_id}: {', '.join(ignored_fields)}")

        # Check if 'price' is provided in the form data
        if "price" in request.form:
            price_str = request.form.get("price")
            # Validate the provided price string
            if price_str is None or price_str == '':
                validation_errors["price"] = "Price cannot be empty if provided for update."
            else:
                try:
                    new_price_float = float(price_str)
                    if new_price_float < 0:
                        validation_errors["price"] = "Price cannot be negative."
                    # Check if the new price is actually different from the original
                    # Use a small tolerance for float comparison if necessary, e.g., abs(new_price_float - original_price_float) > 1e-9
                    elif new_price_float != original_price_float:
                        harvest.price = new_price_float # Update the price on the model instance
                        updated_fields_log.append("price") # Log the field change
                        price_changed = True
                        update_occurred = True
                    else:
                         current_app.logger.info(f"Price submitted for Harvest {harvest_id} ({new_price_float}) is the same as the current price. No price change applied.")

                except (ValueError, TypeError):
                    validation_errors["price"] = f"Invalid data type for price: '{price_str}'."
        else:
            # If 'price' field is missing, this endpoint cannot perform its function
             return jsonify(error={"message": "The 'price' field is required in the form data for this update operation."}), 400

        # If validation errors occurred, return them
        if validation_errors:
            return jsonify(error={"message": "Validation failed during price update.", "details": validation_errors}), 400

        # --- Recalculate total_price if price changed ---
        if price_changed:
            try:
                # Ensure price and accepted quantity exist for calculation
                if harvest.price is not None and harvest.accepted is not None:
                    new_total_price = round(float(harvest.price) * float(harvest.accepted), 2)
                    # Check if the recalculated total price is different (use tolerance if comparing floats)
                    if new_total_price != original_total_price_float:
                        harvest.total_price = new_total_price
                        updated_fields_log.append("total_price (recalculated)")
                        update_occurred = True
                # Handle case where price might be set to null (if allowed by DB schema)
                elif harvest.price is None and harvest.total_price is not None:
                    harvest.total_price = None
                    updated_fields_log.append("total_price (set to null)")
                    update_occurred = True
                # Log if accepted quantity is missing, preventing calculation
                elif harvest.accepted is None:
                     current_app.logger.warning(f"Cannot recalculate total_price for Harvest {harvest_id}: 'accepted' quantity is missing.")

            except Exception as calc_e:
                db.session.rollback() # Rollback if calculation fails
                current_app.logger.error(f"Error recalculating total_price for harvest {harvest_id} during PATCH by admin {admin_email}: {calc_e}", exc_info=True)
                return jsonify(error={"message": f"Failed to recalculate total price. Error: {calc_e}"}), 500

        # --- Check if any update actually happened ---
        if not update_occurred:
            # If no changes were made (e.g., price submitted was the same), return 200 OK
            # We still might want to return the current record for consistency
            current_app.logger.info(f"No effective change detected for Harvest {harvest_id} price/total_price update by admin {admin_email}.")
            # Optionally, call get_harvest_by_id here too for a consistent response format
            # For now, just returning a simple message. Adjust if needed.
            return jsonify(message="No changes detected or applied to harvest price or total price."), 200

        # --- Log, Commit, Notify ---
        # Construct log message detailing changes
        log_parts = []
        if "price" in updated_fields_log:
            log_parts.append(f"price changed from {format_price(original_price_float)} to {format_price(harvest.price)}")
        if "total_price (recalculated)" in updated_fields_log:
            log_parts.append(f"total_price recalculated from {format_price(original_total_price_float)} to {format_price(harvest.total_price)}")
        if "total_price (set to null)" in updated_fields_log:
             log_parts.append(f"total_price changed from {format_price(original_total_price_float)} to null")
        changes_str = '; '.join(log_parts) # Will only contain actual changes

        # Log description indicates admin action but logs against original user context
        log_desc = (f"Harvest '{harvest.name}' (ID: {harvest_id}) price details updated by admin '{admin_email}' (Admin ID: {admin_user.login_id}). "
                    f"Changes: [{changes_str}].")

        # Log using the original user_id associated with the harvest
        update_log = log_harvest_activity(harvest.user_id, harvest.harvest_id, log_desc)
        # CRITICAL: Check if logging failed, rollback if so
        if not update_log:
             db.session.rollback()
             current_app.logger.error(f"Failed to log harvest price update activity (Harvest ID {harvest_id}). Transaction rolled back.")
             return jsonify(error={"message": "Failed to create activity log. Price update not saved."}), 500

        # Commit the changes to the database
        # Note: last_updated timestamp is assumed to be handled by the model (e.g., onupdate=...)
        db.session.commit()
        db.session.refresh(harvest) # Refresh to get the latest state, including DB-updated timestamp
        current_app.logger.info(f"Successfully updated Harvest {harvest_id} price via PATCH by admin {admin_email}. Logged against original user ID: {harvest.user_id}. Last Updated: {harvest.last_updated}")

        # --- Send Notification ---
        notify_payload = {
            "action": "update", "harvest_id": harvest.harvest_id,
            "updated_by_admin": admin_email, # Identify the admin who performed the update
            "updated_fields": updated_fields_log, # List of fields changed
            "price": format_price(harvest.price),
            "total_price": format_price(harvest.total_price),
            "status": harvest.status, # Include current status for context
            "last_updated": format_datetime(harvest.last_updated) # Use corrected helper
        }
        send_notification('harvests_updates', notify_payload)

        # --- Success Response (Using the corrected logic) ---
        # Re-use get_harvest_by_id logic to construct the full response object
        # This ensures the response format is consistent with GET requests
        response_tuple = get_harvest_by_id(harvest_id) # Call the GET endpoint logic internally

        # Check if the call returned the expected structure: (Flask Response object, status_code)
        # ***** THIS IS THE CORRECTED BLOCK *****
        if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and isinstance(response_tuple[0], Response):
            response_object = response_tuple[0]
            status_code = response_tuple[1]

            if status_code == 200: # Check if the internal call was successful
                updated_harvest_data = response_object.json.get('harvest')
                if updated_harvest_data:
                    # Return 200 OK with the updated harvest data
                    return jsonify(
                        message=f"Harvest {harvest_id} price updated successfully by admin.",
                        harvest=updated_harvest_data
                    ), 200
                else:
                    # This case suggests get_harvest_by_id returned 200 but the JSON was malformed
                    current_app.logger.error(f"Failed to parse 'harvest' key from get_harvest_by_id({harvest_id}) JSON after price PATCH (Status 200).")
                    return jsonify(error={"message": "Price updated, but failed to retrieve full updated record structure."}), 500
            else:
                # The internal call get_harvest_by_id itself failed (e.g., returned 404 or 500)
                current_app.logger.error(f"Internal call to get_harvest_by_id({harvest_id}) returned status {status_code} after price PATCH.")
                # Try to forward the error from the internal call
                error_payload = response_object.json # Assuming error responses also use jsonify
                return jsonify(error={"message": "Price updated in database, but failed to retrieve full updated record due to an internal error.", "details": error_payload}), 500

        else: # Handle unexpected return type from internal call (not a tuple, not a Response, wrong length etc.)
             log_content = str(response_tuple)[:200] # Log first 200 chars of unexpected response
             response_type = type(response_tuple)
             response_len = len(response_tuple) if isinstance(response_tuple, tuple) else 'N/A'
             current_app.logger.error(f"Unexpected return type/structure from get_harvest_by_id({harvest_id}) after price PATCH: Type={response_type}, Len={response_len}, Content='{log_content}...'")
             return jsonify(error={"message": "Price updated in database, but failed to retrieve full updated record due to internal response format error."}), 500
        # ***** END OF CORRECTED BLOCK *****

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        status_code = 400 # Default bad request
        msg = f"Database error during price update: {error_detail}"
        current_app.logger.error(f"Database error during PATCH /harvests/{harvest_id} price update by admin {admin_email}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        status_code = 500 # Internal Server Error
        msg = "An unexpected internal server error occurred during the price update."
        current_app.logger.error(f"Unexpected error during PATCH /harvests/{harvest_id} price update by admin {admin_email}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code


# <<< --- NEW PATCH ROUTE FOR STATUS --- >>>
@harvests_api.patch("/harvests/<int:harvest_id>/status")
def update_harvest_status(harvest_id):
    """
    Updates ONLY the status of a harvest record.
    Requires 'user_email' (of the acting user) and 'status' in form data.
    Logs the action against the user identified by 'user_email'.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # --- Get Required Form Data ---
    user_email = request.form.get("user_email") # User performing the status update
    new_status = request.form.get("status") # The desired new status

    # --- Basic Input Validation ---
    if not user_email:
        return jsonify(error={"message": "User email ('user_email') is required to log the status update."}), 400
    if not new_status:
        return jsonify(error={"message": "New status ('status') is required in form data."}), 400

    # --- Validate User ---
    # Find the user performing the action based on the provided email
    user = Users.query.filter(Users.email.ilike(user_email)).first()
    if not user:
        return jsonify(error={"message": f"User with email '{user_email}' not found."}), 404
    if not user.isActive:
        return jsonify(error={"message": f"User '{user_email}' is not active."}), 403
    # Add role checks here if needed (e.g., only specific roles can set status to 'Sold'/'Spoiled')
    # Example: if new_status == 'Sold' and user.role != 'Sales': return jsonify(...), 403

    # --- Validate Status ---
    # Ensure the provided status is one of the allowed values
    if new_status not in ALLOWED_HARVEST_STATUSES:
        return jsonify(error={"message": f"Invalid status '{new_status}'. Allowed statuses: {', '.join(ALLOWED_HARVEST_STATUSES)}."}), 400

    try:
        # --- Get Harvest Record ---
        # Fetch the harvest record to be updated
        harvest = db.session.get(Harvest, harvest_id)
        if not harvest:
            return jsonify(message=f"Harvest with ID {harvest_id} not found."), 404

        # Check if the user ID exists on the harvest record (for logging consistency)
        if harvest.user_id is None:
             current_app.logger.warning(f"Harvest {harvest_id} is missing original user_id, proceeding with status update by {user_email}.")
             # Decide if this should be an error or just a warning

        # --- Check if Status Changed ---
        original_status = harvest.status
        if new_status == original_status:
            # If the status is already the desired status, no update needed
            current_app.logger.info(f"Harvest {harvest_id} status is already '{new_status}'. No update performed by user {user_email}.")
            # Return the current record for consistency
            response_tuple = get_harvest_by_id(harvest_id)
            if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and isinstance(response_tuple[0], Response) and response_tuple[1] == 200:
                 return jsonify(
                    message=f"Harvest {harvest_id} status is already '{new_status}'. No update performed.",
                    harvest=response_tuple[0].json.get('harvest')
                 ), 200
            else:
                 # Fallback if getting the record fails unexpectedly
                 return jsonify(message=f"Harvest {harvest_id} status is already '{new_status}'. No update performed."), 200


        # --- Update Status ---
        harvest.status = new_status
        # The last_updated field should be updated automatically if configured in the model (e.g., onupdate=func.now())

        # --- Log Activity ---
        # Log the status change against the user performing the action (from user_email)
        log_desc = (f"Harvest '{harvest.name}' (ID: {harvest_id}) status updated from '{original_status}' to '{new_status}' "
                    f"by user {user.first_name} {user.last_name} ({user.email}, ID: {user.user_id}).")
        # Use the acting user's ID for the log
        status_update_log = log_harvest_activity(user.user_id, harvest_id, log_desc)
        # CRITICAL: Check if logging failed, rollback if so
        if not status_update_log:
             db.session.rollback()
             current_app.logger.error(f"Failed to log harvest status update activity (Harvest ID {harvest_id}). Transaction rolled back.")
             return jsonify(error={"message": "Failed to create activity log. Status update not saved."}), 500

        # --- Commit and Notify ---
        db.session.commit()
        db.session.refresh(harvest) # Refresh to get DB-updated timestamp
        current_app.logger.info(f"Successfully updated Harvest {harvest_id} status to '{new_status}' by user {user.email}. Last Updated: {harvest.last_updated}")

        # Send notification about the status update
        send_notification('harvests_updates', {
            "action": "update", "harvest_id": harvest.harvest_id,
            "updated_by_user": user.email, # User who performed the update
            "updated_fields": ["status"], # Field that changed
            "status": harvest.status, # The new status
            "last_updated": format_datetime(harvest.last_updated) # Use corrected helper
        })

        # --- Success Response ---
        # Re-use get_harvest_by_id logic to construct the full response object
        response_tuple = get_harvest_by_id(harvest_id)
        # Apply the same robust checking as in the price update endpoint
        if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and isinstance(response_tuple[0], Response):
            response_object = response_tuple[0]
            status_code = response_tuple[1]
            if status_code == 200:
                updated_harvest_data = response_object.json.get('harvest')
                if updated_harvest_data:
                    return jsonify(
                        message=f"Harvest {harvest_id} status updated successfully to '{new_status}'.",
                        harvest=updated_harvest_data
                    ), 200
                else:
                    current_app.logger.error(f"Failed to parse 'harvest' key from get_harvest_by_id({harvest_id}) JSON after status PATCH (Status 200).")
                    return jsonify(error={"message": "Status updated, but failed to retrieve full updated record structure."}), 500
            else:
                current_app.logger.error(f"Internal call to get_harvest_by_id({harvest_id}) returned status {status_code} after status PATCH.")
                error_payload = response_object.json
                return jsonify(error={"message": "Status updated in database, but failed to retrieve full updated record due to an internal error.", "details": error_payload}), 500
        else:
             log_content = str(response_tuple)[:200]
             response_type = type(response_tuple)
             response_len = len(response_tuple) if isinstance(response_tuple, tuple) else 'N/A'
             current_app.logger.error(f"Unexpected return type/structure from get_harvest_by_id({harvest_id}) after status PATCH: Type={response_type}, Len={response_len}, Content='{log_content}...'")
             return jsonify(error={"message": "Status updated in database, but failed to retrieve full updated record due to internal response format error."}), 500

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        status_code = 400 # Default bad request
        msg = f"Database error during status update: {error_detail}"
        current_app.logger.error(f"Database error during PATCH /harvests/{harvest_id}/status by user {user_email}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        status_code = 500 # Internal Server Error
        msg = "An unexpected internal server error occurred during the status update."
        current_app.logger.error(f"Unexpected error during PATCH /harvests/{harvest_id}/status by user {user_email}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code


# --- DELETE /harvests/<id> ---
@harvests_api.delete("/harvests/<int:harvest_id>")
def delete_harvest(harvest_id):
    """
    Deletes a specific harvest record by its ID.
    No user email is required in the request body/args for the deletion action itself.
    Deletion activity is logged to the application logger only.
    Requires API Key for basic authorization.
    Attempts to revert the associated plant's status if applicable and logs this revert.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # Note: User email is intentionally NOT required/used here for the *action* of deletion.
    # Authorization is handled by the API Key. Logging context is limited.

    try:
        # --- Get Harvest Record ---
        # Fetch the harvest record to be deleted
        # Using with_for_update=True could lock the row if high concurrency is expected,
        # but might be overkill depending on usage patterns. db.session.get is usually sufficient.
        harvest = db.session.get(Harvest, harvest_id)
        if not harvest:
            return jsonify(message=f"Harvest with ID {harvest_id} not found."), 404

        # Store details *before* deletion for logging/notification/plant revert
        plant_id_ref = harvest.plant_id
        gh_id_ref = harvest.greenhouse_id
        harvest_name_ref = harvest.name
        plant_name_ref = harvest.plant_name
        original_user_id = harvest.user_id # Needed if we revert plant status and want to log that against the original user

        # --- Log Deletion Attempt (Application Logger Only) ---
        # Log the intent to delete, noting the lack of specific user context for the *action*
        log_desc = (f"Attempting deletion of Harvest record (ID: {harvest_id}, Name: '{harvest_name_ref}', "
                    f"Plant: '{plant_name_ref}' ID:{plant_id_ref}, Original UserID: {original_user_id}) "
                    f"via API request (API Key validated).")
        current_app.logger.info(log_desc)

        # --- Attempt to Revert Plant Status ---
        reverted_plant = False
        new_plant_status = None
        original_plant_status = None
        planted_crop = None
        if plant_id_ref: # Check if there is a plant associated
            planted_crop = db.session.get(PlantedCrops, plant_id_ref)
            # Only revert if the plant exists and is currently marked 'harvested'
            if planted_crop and planted_crop.status == "harvested":
                 original_plant_status = planted_crop.status
                 # Define what status to revert to (e.g., 'not harvested', 'available', etc.)
                 # ***** IMPORTANT: Choose the correct status to revert to *****
                 planted_crop.status = "not harvested" # <<< CHANGE THIS to the appropriate pre-harvest status if needed
                 new_plant_status = planted_crop.status
                 db.session.add(planted_crop) # Add updated plant to session for commit
                 reverted_plant = True
                 current_app.logger.info(f"Marked Plant {plant_id_ref} status for revert from 'harvested' to '{new_plant_status}' due to Harvest {harvest_id} deletion.")

                 # Log the plant status change - requires a user_id.
                 # If original_user_id exists, log against them, noting the trigger was API deletion.
                 if original_user_id:
                     log_plant_revert_desc = (f"Status reverted from '{original_plant_status}' to '{new_plant_status}' "
                                              f"due to deletion of associated Harvest ID {harvest_id} ('{harvest_name_ref}') via API (no acting user context).")
                     # Ensure log_planted_crop_activity handles DB session appropriately or call flush/commit later
                     # Note: This might commit the plant change separately if log_planted_crop_activity commits.
                     # It's generally better to commit everything together at the end.
                     # Consider modifying log_planted_crop_activity to not commit, or just log here.
                     log_planted_crop_activity(original_user_id, plant_id_ref, log_plant_revert_desc)
                 else:
                      # If the original harvest record didn't have a user_id, we can't log against a user context
                      current_app.logger.warning(f"Cannot log plant status revert for Plant {plant_id_ref} as original harvest user ID is missing.")

            elif planted_crop:
                 # Log if plant exists but status wasn't 'harvested'
                 current_app.logger.warning(f"Harvest {harvest_id} deleted, but associated Plant {plant_id_ref} status was '{planted_crop.status}', not 'harvested'. Status not reverted.")
            else:
                 # Log if the associated plant record was not found
                 current_app.logger.warning(f"Associated Planted Crop with ID {plant_id_ref} not found when deleting Harvest {harvest_id}. Cannot revert status.")
        else:
            # Log if the harvest wasn't linked to a plant_id
             current_app.logger.info(f"Harvest {harvest_id} deleted. No associated plant_id found, no plant status to revert.")


        # --- Delete Harvest Record ---
        # Cascade="all, delete-orphan" on Harvest.activity_logs relationship in the model
        # should automatically delete associated HarvestActivityLogs. If not configured,
        # manual deletion would be needed here BEFORE deleting the harvest.
        # Example: HarvestActivityLogs.query.filter_by(harvest_id=harvest_id).delete()
        db.session.delete(harvest)

        # --- Commit Transaction ---
        # This commits both the harvest deletion and the plant status update (if applicable)
        db.session.commit()
        current_app.logger.info(f"Successfully committed deletion of Harvest {harvest_id}. Plant status reverted: {reverted_plant}")

        # --- Notifications ---
        # Notify about the harvest deletion
        send_notification('harvests_updates', {
            "action": "delete",
            "harvest_id": harvest_id,
            "plant_id": plant_id_ref, # Include related IDs for context
            "gh_id": gh_id_ref,
            "deleted_by": "API Request (No User Context)" # Indicate lack of user info for the action
        })
        # Notify about the plant status change if it happened
        if reverted_plant and planted_crop:
            send_notification('planted_crops_updates', {
                "action": "update",
                "plant_id": plant_id_ref,
                "updated_fields": ["status"],
                "new_status": new_plant_status, # Send the status it was reverted TO
                "triggered_by": f"harvest_delete:{harvest_id}"
            })

        return jsonify(message=f"Harvest {harvest_id} ('{harvest_name_ref}') deleted successfully. Plant status reverted: {reverted_plant}."), 200

    except IntegrityError as e:
        db.session.rollback() # Rollback on integrity errors
        error_detail = str(getattr(e, 'orig', str(e)))
        current_app.logger.error(f"Database Integrity error deleting harvest {harvest_id}: {e}", exc_info=True)
        # Try to provide a more user-friendly message about blocking constraints
        blocking_table = "related records"
        if 'foreign key constraint' in error_detail.lower():
             # Example: Check if 'sales' table is mentioned (adjust based on actual FK names)
             if 'sale' in error_detail.lower() or 'sales_harvest_id_fkey' in error_detail.lower():
                  blocking_table = "associated Sales records"
             # Add checks for other potential dependencies (e.g., rejections, processing steps)
        msg = f"Cannot delete harvest {harvest_id} because it is referenced by existing {blocking_table}. Please remove dependent records first."
        status_code = 409 # Conflict - cannot delete due to dependencies
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback() # Rollback on any other unexpected error
        current_app.logger.error(f"Unexpected error deleting harvest {harvest_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred during harvest deletion."}), 500


# <<< --- NEW: DELETE ALL HARVESTS ROUTE (NO USER EMAIL REQUIRED) --- >>>
@harvests_api.delete("/harvests")
def delete_all_harvests():
    """
    Deletes ALL harvest records and their associated logs.
    Requires confirmation parameter '?confirm=true'.
    No user identification required for this action beyond API Key.
    WARNING: This does NOT attempt to revert associated PlantedCrops statuses.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error


    try:
        # Log the attempt before deletion
        current_app.logger.warning("Attempting bulk deletion of ALL harvest records via API Key.")
        current_app.logger.warning("Associated PlantedCrops statuses will NOT be reverted by this operation.")

        # Assuming cascade delete is set up for HarvestActivityLogs related to Harvest.
        # If not, delete logs first (potentially very slow for large tables):
        # num_logs_deleted = HarvestActivityLogs.query.delete(synchronize_session=False)
        # current_app.logger.info(f"Queued deletion of {num_logs_deleted} harvest activity logs.")

        # Delete all harvest records
        # It's often safer and faster to delete logs first if cascade isn't guaranteed or if there are triggers/complexities
        num_logs_deleted = db.session.query(HarvestActivityLogs).delete(synchronize_session=False)
        current_app.logger.info(f"Queued deletion of {num_logs_deleted} harvest activity logs.")
        num_harvests_deleted = db.session.query(Harvest).delete(synchronize_session=False)
        current_app.logger.info(f"Queued deletion of {num_harvests_deleted} harvest records.")

        # Commit the transaction
        db.session.commit()
        log_msg = f"COMMITTED bulk deletion of {num_harvests_deleted} harvest records and {num_logs_deleted} associated logs."
        current_app.logger.warning(log_msg) # Keep as warning due to destructive nature

        # Send summary notification
        try:
            send_notification('harvests_updates', {
                "action": "delete_all",
                "harvests_deleted_count": num_harvests_deleted,
                "logs_deleted_count": num_logs_deleted, # If manually deleted
                "deleted_by": "System/API Key" # Indicate it wasn't a specific user
            })
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send delete_all notification for harvests: {notify_e}", exc_info=True)

        return jsonify(
            message=f"Successfully deleted {num_harvests_deleted} harvest records and {num_logs_deleted} associated logs. Associated plant statuses were NOT reverted."
        ), 200

    except IntegrityError as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', e))
        current_app.logger.error(f"Integrity error during bulk harvest deletion: {e}", exc_info=True)
        # Check if it's a foreign key constraint violation
        # This check might be less reliable if logs were deleted first
        msg = "Cannot delete all harvest records due to database integrity constraints (potentially dependencies from other tables like Sales)."
        if 'violates foreign key constraint' in error_detail.lower():
             # Check for common dependencies like 'sales'
             if 'sale' in error_detail.lower() or 'sales_harvest_id_fkey' in error_detail.lower():
                  blocking_table = "associated Sales records"
                  msg = f"Cannot delete all harvest records due to existing database references (e.g., {blocking_table}). Please remove dependent records first."
             else:
                  blocking_table = "other related records"
                  msg = f"Cannot delete all harvest records due to existing database references to {blocking_table}. Please remove dependent records first."

        return jsonify(error={"message": msg, "detail": error_detail}), 409 # Use 409 Conflict
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all harvest records: {e}", exc_info=True)
        return jsonify(error={"message": "An error occurred during bulk deletion."}), 500
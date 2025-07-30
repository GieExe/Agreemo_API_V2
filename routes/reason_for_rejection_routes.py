# C:\Users\Giebert\PcharmProjects\agreemo_api_v2\routes\reason_for_rejection_routes.py
import os
from flask import Blueprint, request, jsonify, current_app, Response # Ensure Response is imported
import pytz
import json
import psycopg2
from datetime import datetime, date # Ensure date is imported
from decimal import Decimal, InvalidOperation # Keep for precise calculations if needed

from db import db
# Ensure correct model imports based on your project structure
from models.reason_for_rejection_model import ReasonForRejection
from models.greenhouses_model import Greenhouse
from models.users_model import Users # Ensure Users model is imported
# --- Import AdminUser for admin-specific actions ---
from models.admin_user_model import AdminUser
# --- End Import ---
from models.planted_crops_model import PlantedCrops
from models.activity_logs.rejection_activity_logs_model import RejectionActivityLogs
# Import for DB specific errors if needed
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy import func # Import func for potential future use if needed


reason_for_rejection_api = Blueprint("reason_for_rejection_api", __name__)

# --- Configuration ---
# Use environment variables in production for API_KEY
API_KEY = os.environ.get("API_KEY", "YOUR_DEFAULT_FALLBACK_API_KEY") # Replace default
PH_TZ = pytz.timezone('Asia/Manila')
ALLOWED_REJECTION_TYPES = ["too_small", "physically_damaged", "diseased"] # Define allowed types for creation
# Define allowed statuses for creation and update
ALLOWED_REJECTION_STATUSES = ["Not Sold", "Sold", "Disposed", "Processing"]


# --- Helper Functions ---
def check_api_key(request):
    """Checks if the provided API key in the header is valid."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        current_app.logger.warning(f"Failed API Key attempt from IP: {request.remote_addr}")
        return jsonify(error={"Not Authorised": "Incorrect or missing api_key."}), 403
    return None

def format_date(d):
    """Formats date or datetime objects to YYYY-MM-DD string."""
    if not d: return None
    if isinstance(d, datetime): d = d.date() # Get date part if datetime
    if isinstance(d, date):
        try: return d.strftime("%Y-%m-%d")
        except ValueError: # Handle potential date range issues
            current_app.logger.warning(f"Could not format date {d} with strftime.")
            return str(d)
    current_app.logger.warning(f"format_date received unexpected type: {type(d)}, value: {d}")
    return str(d) # Fallback

def format_price(p):
    """Safely formats a price value (numeric type) to float for JSON, handles None."""
    if p is None: return None
    try:
        # Use float for JSON serialization consistency
        return float(p)
    except (ValueError, TypeError):
        current_app.logger.warning(f"Could not format price value {p} as float.")
        return None # Or handle as error depending on requirements

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
                 conn.close()
                 return
            curs.execute(f"NOTIFY {channel}, %s;", (json_payload,))
        conn.close()
        current_app.logger.info(f"Sent notification to channel '{channel}'. Payload: {json_payload}")
    except psycopg2.Error as db_err:
        current_app.logger.error(f"Database error sending notification to channel '{channel}': {db_err}", exc_info=True)
        if 'conn' in locals() and conn: conn.close() # Ensure connection is closed on error
    except TypeError as json_err:
         current_app.logger.error(f"JSON serialization error for notification payload to channel '{channel}': {json_err}. Payload: {payload}", exc_info=True)
         if 'conn' in locals() and conn: conn.close()
    except Exception as e:
        current_app.logger.error(f"Unexpected error sending notification to channel '{channel}': {e}", exc_info=True)
        if 'conn' in locals() and conn: conn.close()


def log_rejection_activity(user_id, rejection_id, description):
    """
    Creates and adds a rejection activity log, linked to users.user_id.
    Returns the log object on success, None on failure.
    """
    if user_id is None:
        current_app.logger.error(f"Attempted log RejectionActivityLog with NULL user_id for rejection {rejection_id}.")
        return None # Indicate failure

    try:
        # Use timezone-aware timestamp for logging
        log_time_aware = datetime.now(PH_TZ) # Use local PH time
        # Or use UTC: log_time_aware = datetime.now(pytz.utc)

        new_log = RejectionActivityLogs(
            login_id=user_id, # This MUST be a valid foreign key to users.user_id
            rejection_id=rejection_id,
            logs_description=description,
            log_date=log_time_aware
        )
        db.session.add(new_log)
        db.session.flush() # Assigns log_id

        current_app.logger.info(f"Prepared RejectionActivityLog ID {new_log.log_id} for rejection {rejection_id}, user {user_id}.")
        # Notification is sent separately after commit in the calling function typically
        return new_log # Return the log object on success

    except IntegrityError as ie:
        db.session.rollback() # Rollback on integrity error during logging attempt
        # Check if the error is due to a non-existent user_id (FK violation)
        if 'rejection_activity_logs_login_id_fkey' in str(ie) or \
           ('foreign key constraint' in str(ie).lower() and 'login_id' in str(ie).lower()):
            current_app.logger.error(f"CRITICAL: Foreign key violation (rejection_activity_logs_login_id_fkey) trying to log activity for rejection {rejection_id}. The user ID '{user_id}' provided does NOT exist in the 'users' table. Description: '{description}'", exc_info=True)
        else:
            # Log other integrity errors
            current_app.logger.error(f"Database integrity error preparing rejection log for rejection {rejection_id} (User ID: {user_id}): {ie}", exc_info=True)
        return None # Indicate logging failed

    except Exception as e:
        db.session.rollback() # Rollback on any other error during logging
        current_app.logger.error(f"Unexpected error preparing activity log for rejection {rejection_id} (User ID: {user_id}): {e}", exc_info=True)
        return None # Indicate logging failed

# --- Routes ---

# <<< --- GET ALL ROUTE --- >>>
@reason_for_rejection_api.get("/reason_for_rejection")
def get_all_reasons_for_rejection():
    """
    Gets all reason for rejection records, including the name of the user
    associated with the creation log entry, and the rejection status.
    Supports filtering by greenhouse_id.
    Does NOT include greenhouse_name.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        greenhouse_id_filter = request.args.get('greenhouse_id', type=int)

        # Query includes join to get user name from log
        query = db.session.query(
            ReasonForRejection,
            Users.first_name,
            Users.last_name
        ).select_from(ReasonForRejection).outerjoin(
            RejectionActivityLogs,
            (RejectionActivityLogs.rejection_id == ReasonForRejection.rejection_id) &
            # Be specific about the creation log message if possible
            (RejectionActivityLogs.logs_description.like('Rejection record added%')) # Match log description for creation
        ).outerjoin(
            Users, Users.user_id == RejectionActivityLogs.login_id
        ).options(
            # Eager load related PlantedCrops, but not Greenhouse
            db.joinedload(ReasonForRejection.planted_crops)
            # db.joinedload(ReasonForRejection.greenhouses) # Greenhouse name removed
        )

        if greenhouse_id_filter:
            query = query.filter(ReasonForRejection.greenhouse_id == greenhouse_id_filter)

        # Order results meaningfully
        query_results = query.order_by(ReasonForRejection.rejection_date.desc(), ReasonForRejection.rejection_id.desc()).all()

        status_code = 200
        count = len(query_results)
        message = f"Successfully retrieved {count} rejection record(s)."
        if count == 0:
            message = f"No rejection records found for greenhouse {greenhouse_id_filter}." if greenhouse_id_filter else "No reason for rejection records found."

        rejection_list = []
        processed_ids = set() # Handle potential duplicate logs matching criteria
        for reason, first_name, last_name in query_results:
            if reason.rejection_id in processed_ids: continue # Skip if already processed due to multiple logs
            processed_ids.add(reason.rejection_id)

            added_by_user_name = f"{first_name} {last_name}".strip() if first_name or last_name else "Unknown User"
            plant_name = reason.plant_name
            # Fallback if plant_name wasn't stored on the rejection record itself
            if not plant_name and reason.planted_crops:
                plant_name = reason.planted_crops.plant_name

            rejection_list.append({
                "rejection_id": reason.rejection_id,
                "greenhouse_id": reason.greenhouse_id,
                # "greenhouse_name": reason.greenhouses.name if reason.greenhouses else None, # Removed
                "plant_id": reason.plant_id,
                "plant_name": plant_name,
                "name": added_by_user_name, # User who added the rejection
                "type": reason.type,
                "quantity": reason.quantity,
                "rejection_date": format_date(reason.rejection_date),
                "comments": reason.comments,
                "price": format_price(reason.price),
                "deduction_rate": format_price(reason.deduction_rate),
                "total_price": format_price(reason.total_price),
                "status": reason.status
            })

        # Recalculate count based on processed IDs
        final_count = len(rejection_list)
        message = f"Successfully retrieved {final_count} rejection record(s)." # Update message with final count
        if final_count == 0:
             message = f"No rejection records found for greenhouse {greenhouse_id_filter}." if greenhouse_id_filter else "No reason for rejection records found."


        current_app.logger.info(f"GET /reason_for_rejection: {message} (Filter GH: {greenhouse_id_filter})")
        return jsonify(message=message, count=final_count, reasons_for_rejection=rejection_list), status_code
    except Exception as e:
        current_app.logger.error(f"Error during GET /reason_for_rejection: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching rejection records."}), 500


# <<< --- GET BY ID ROUTE --- >>>
@reason_for_rejection_api.get("/reason_for_rejection/<int:rejection_id>")
def get_reason_for_rejection_by_id(rejection_id):
    """
    Gets a specific reason for rejection record by its ID, including the name
    of the user associated with the creation log entry, and the rejection status.
    Does NOT include greenhouse_name. Returns tuple: (jsonify(data), status_code)
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        # Query includes join to get user name from log
        # We use first() so potential multiple logs for creation don't cause issues here,
        # but it might pick an arbitrary user if multiple 'added' logs exist for the same user.
        result = db.session.query(
            ReasonForRejection,
            Users.first_name,
            Users.last_name
        ).select_from(ReasonForRejection).outerjoin(
            RejectionActivityLogs,
            (RejectionActivityLogs.rejection_id == ReasonForRejection.rejection_id) &
            (RejectionActivityLogs.logs_description.like('Rejection record added%')) # Match log description for creation
        ).outerjoin(
            Users, Users.user_id == RejectionActivityLogs.login_id
        ).options(
            # Eager load related PlantedCrops, but not Greenhouse
            db.joinedload(ReasonForRejection.planted_crops)
            # db.joinedload(ReasonForRejection.greenhouses) # Greenhouse name removed
        ).filter(
            ReasonForRejection.rejection_id == rejection_id
        ).first() # Take the first matching log/user for the creator name

        if not result:
            current_app.logger.warning(f"ReasonForRejection ID {rejection_id} not found.")
            # Return as tuple for internal calls that expect it
            return jsonify(message=f"Reason for rejection with ID {rejection_id} not found"), 404

        reason, first_name, last_name = result
        added_by_user_name = f"{first_name} {last_name}".strip() if first_name or last_name else "Unknown User"
        plant_name = reason.plant_name
        # Fallback if plant_name wasn't stored on the rejection record itself
        if not plant_name and reason.planted_crops:
            plant_name = reason.planted_crops.plant_name

        reason_data = {
            "rejection_id": reason.rejection_id,
            "greenhouse_id": reason.greenhouse_id,
            # "greenhouse_name": reason.greenhouses.name if reason.greenhouses else None, # Removed
            "plant_id": reason.plant_id,
            "plant_name": plant_name,
            "name": added_by_user_name, # User who added the rejection
            "type": reason.type,
            "quantity": reason.quantity,
            "rejection_date": format_date(reason.rejection_date),
            "comments": reason.comments,
            "price": format_price(reason.price),
            "deduction_rate": format_price(reason.deduction_rate),
            "total_price": format_price(reason.total_price),
            "status": reason.status
        }
        current_app.logger.info(f"Successfully fetched ReasonForRejection ID {rejection_id}.")
        # Return as tuple for internal calls
        return jsonify(reason_for_rejection=reason_data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching rejection record ID {rejection_id}: {e}", exc_info=True)
        # Return as tuple for internal calls
        return jsonify(error={"message": "An internal server error occurred while fetching the rejection record."}), 500


# <<< --- POST ROUTE --- >>>
@reason_for_rejection_api.post("/reason_for_rejection")
def add_reason_for_rejection():
    """
    Adds a new reason for rejection record using data from request.form.
    Calculates total_price. Logs user activity.
    Accepts an optional 'status' field, defaulting to 'Not Sold'.
    Requires 'email' in form data to identify the user performing the action.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # --- Extract data from request.form ---
    greenhouse_id_str = request.form.get("greenhouse_id")
    plant_id_str = request.form.get("plant_id")
    email = request.form.get("email") # Required for logging
    rejection_type = request.form.get("type")
    quantity_str = request.form.get("quantity")
    rejection_date_str = request.form.get("rejection_date") # Format: YYYY-MM-DD
    price_str = request.form.get("price")
    deduction_rate_str = request.form.get("deduction_rate")
    comments = request.form.get("comments", "")
    # --- Get optional status from form ---
    status_from_form = request.form.get("status")
    # --- End Get Status ---

    # --- Validation ---
    errors = {}
    required_fields = {
        "greenhouse_id": greenhouse_id_str, "plant_id": plant_id_str,
        "email": email, "type": rejection_type, "quantity": quantity_str,
        "rejection_date": rejection_date_str, "price": price_str,
        "deduction_rate": deduction_rate_str
        # status is optional
    }
    missing = [name for name, value in required_fields.items() if not value]
    if missing:
        errors['missing_fields'] = f"Missing required form fields: {', '.join(missing)}"

    # Validate user first
    user = None
    if email:
        user = Users.query.filter(Users.email.ilike(email)).first()
        if not user: errors['email'] = f"User with email '{email}' not found."
        elif not user.isActive: errors['user_status'] = f"User '{email}' is not active."
    # No 'else' here because missing email is caught by required_fields check

    # Early exit if required fields missing or user invalid
    if missing or 'email' in errors or 'user_status' in errors:
         return jsonify(error={"message": "Validation failed.", "details": errors}), 400

    # Initialize variables
    greenhouse = None; plant = None; rejection_date_obj = None
    greenhouse_id = None; plant_id = None; quantity = None; price_float = None; deduction_rate_float = None; calculated_total_price = None
    final_status = 'Not Sold' # Default status

    # --- Validate Status (if provided) ---
    if status_from_form and status_from_form.strip():
        provided_status = status_from_form.strip()
        if provided_status not in ALLOWED_REJECTION_STATUSES:
            errors['status'] = f"Invalid status '{provided_status}'. Allowed statuses: {', '.join(ALLOWED_REJECTION_STATUSES)}."
        else:
            final_status = provided_status # Use validated status
    # --- End Validate Status ---

    # Validate rejection type
    if rejection_type and rejection_type not in ALLOWED_REJECTION_TYPES:
        errors['type'] = f"Invalid rejection type '{rejection_type}'. Allowed types: {', '.join(ALLOWED_REJECTION_TYPES)}."

    # Validate and convert numeric fields and date
    try:
        try: greenhouse_id = int(greenhouse_id_str)
        except (ValueError, TypeError): errors['greenhouse_id'] = "Greenhouse ID must be a valid integer."
        try: plant_id = int(plant_id_str)
        except (ValueError, TypeError): errors['plant_id'] = "Plant ID must be a valid integer."

        try:
            quantity = int(quantity_str)
            if quantity <= 0: errors['quantity'] = "Quantity must be a positive integer."
        except (ValueError, TypeError): errors['quantity'] = "Quantity must be a valid integer."

        try:
            price_float = float(price_str)
            if price_float < 0: errors['price'] = "Price cannot be negative."
        except (ValueError, TypeError): errors['price'] = "Price must be a valid number."

        try:
            deduction_rate_float = float(deduction_rate_str)
            if not (0 <= deduction_rate_float <= 100):
                errors['deduction_rate'] = "Deduction rate must be between 0 and 100."
        except (ValueError, TypeError): errors['deduction_rate'] = "Deduction rate must be a valid number."

        try:
            rejection_date_obj = date.fromisoformat(rejection_date_str)
        except (ValueError, TypeError): errors['rejection_date'] = "Invalid date format. Use YYYY-MM-DD."

        # Validate Foreign Keys and Consistency (only if IDs are valid integers)
        if 'greenhouse_id' not in errors and greenhouse_id is not None:
            greenhouse = db.session.get(Greenhouse, greenhouse_id)
            if not greenhouse: errors['greenhouse_id_invalid'] = f"Greenhouse ID {greenhouse_id} not found."

        if 'plant_id' not in errors and plant_id is not None:
            plant = db.session.get(PlantedCrops, plant_id)
            if not plant: errors['plant_id_invalid'] = f"Planted crop ID {plant_id} not found."
            # Check consistency only if both greenhouse and plant lookups succeeded
            elif greenhouse and plant.greenhouse_id != greenhouse_id:
                errors['plant_consistency'] = f"Plant {plant_id} ('{plant.plant_name}') not found in Greenhouse {greenhouse_id}."

        # Calculate Total Price (only if numeric fields are valid)
        if 'quantity' not in errors and 'price' not in errors and 'deduction_rate' not in errors and \
           quantity is not None and price_float is not None and deduction_rate_float is not None:
            try:
                 # Explicitly cast to float before calculation for safety
                 calculated_total_price = round(float(quantity) * float(price_float) * (1.0 - (float(deduction_rate_float) / 100.0)), 2)
            except Exception as calc_e:
                 errors['total_price_calc'] = f"Error calculating total price: {calc_e}"
                 current_app.logger.error(f"Error calculating total_price: Qty={quantity}, Price={price_float}, Rate={deduction_rate_float} -> {calc_e}")

        # Final check for any validation errors accumulated
        if errors:
            current_app.logger.warning(f"Validation errors adding rejection record: {errors}")
            return jsonify(error={"message": "Validation failed.", "details": errors}), 400

        # --- Create and Commit ---
        new_rejection = ReasonForRejection(
            greenhouse_id=greenhouse_id,
            plant_id=plant_id,
            plant_name=plant.plant_name if plant else None, # Get plant name from plant object
            type=rejection_type,
            quantity=quantity,
            rejection_date=rejection_date_obj,
            comments=comments,
            price=price_float, # Store as float/numeric in DB
            deduction_rate=deduction_rate_float, # Store as float/numeric in DB
            total_price=calculated_total_price, # Store as float/numeric in DB
            # --- Set Status Explicitly ---
            status=final_status # Use validated or default status
            # --- End Set Status ---
        )
        db.session.add(new_rejection)
        db.session.flush() # Get the rejection_id

        # Log the activity
        log_description = (f"Rejection record added: Plant '{new_rejection.plant_name}', "
                           f"Type: {rejection_type}, Qty: {quantity}, Ded. Rate: {deduction_rate_float}%. Status set to: {final_status}. "
                           f"Logged by user {user.first_name} {user.last_name} ({user.email}).")
        # Pass user_id from the validated user object
        new_log = log_rejection_activity(
            user_id=user.user_id, rejection_id=new_rejection.rejection_id, description=log_description
        )
        if not new_log:
             # Rollback if logging failed (log_rejection_activity already rolled back its attempt)
             db.session.rollback() # Ensure main transaction is rolled back
             current_app.logger.error(f"Failed to create activity log for rejection add (Rejection ID tentatively {new_rejection.rejection_id}). Transaction rolled back.")
             # Return 500 as logging failure prevented operation
             return jsonify(error={"message": "Failed to create activity log. Rejection record not added."}), 500

        # Commit the main transaction (rejection and log)
        db.session.commit()
        db.session.refresh(new_rejection) # Get DB defaults/updates if any
        current_app.logger.info(f"Successfully added ReasonForRejection ID: {new_rejection.rejection_id} by user {user.email}. Status: {new_rejection.status}")

        # --- Send Notifications (After successful commit) ---
        send_notification('rejection_updates', {
            "action": "insert", "rejection_id": new_rejection.rejection_id,
            "greenhouse_id": new_rejection.greenhouse_id, "plant_id": new_rejection.plant_id,
            "plant_name": new_rejection.plant_name, "type": new_rejection.type, "quantity": new_rejection.quantity,
            "price": format_price(new_rejection.price), "deduction_rate": format_price(new_rejection.deduction_rate),
            "total_price": format_price(new_rejection.total_price),
            "status": new_rejection.status # Include status
        })
        # Send log notification using the committed log ID
        send_notification('rejection_logs_updates', {
            "action": "insert", "log_id": new_log.log_id,
            "rejection_id": new_rejection.rejection_id, "user_id": user.user_id,
            "description": log_description # Send the same description
        })

        # --- Success Response ---
        # Construct response mirroring the GET endpoints (without greenhouse_name)
        created_rejection_response = {
                "rejection_id": new_rejection.rejection_id,
                "greenhouse_id": new_rejection.greenhouse_id,
                "plant_id": new_rejection.plant_id,
                "plant_name": new_rejection.plant_name,
                "type": new_rejection.type,
                "quantity": new_rejection.quantity,
                "rejection_date": format_date(new_rejection.rejection_date),
                "comments": new_rejection.comments,
                "price": format_price(new_rejection.price),
                "deduction_rate": format_price(new_rejection.deduction_rate),
                "total_price": format_price(new_rejection.total_price),
                "status": new_rejection.status # Return actual status
            }
        # Add user name based on the logged action
        created_rejection_response['name'] = f"{user.first_name} {user.last_name}".strip() if user.first_name or user.last_name else "Unknown User"

        return jsonify(
            message="New reason for rejection data successfully added.",
            # rejection_id=new_rejection.rejection_id, # Included in the object below
            reason_for_rejection=created_rejection_response # Changed key for consistency
        ), 201

    except (IntegrityError, DataError) as e:
         db.session.rollback() # Rollback on DB errors
         error_detail = str(getattr(e, 'orig', str(e))) # Get specific DB error
         status_code = 400 # Default Bad Request
         msg = f"Database error: {error_detail}"
         if isinstance(e, IntegrityError):
             status_code = 409 # Conflict for integrity issues
             if 'violates not-null constraint' in error_detail.lower() and 'status' in error_detail.lower():
                  msg = "Database error: 'status' cannot be null. Please ensure a default or provide a valid status."
             elif 'violates foreign key constraint' in error_detail.lower():
                  # Give more context if possible (e.g., check constraint name)
                  if 'greenhouse_id' in error_detail.lower(): fk_field = "greenhouse ID"
                  elif 'plant_id' in error_detail.lower(): fk_field = "plant ID"
                  else: fk_field = "reference ID"
                  msg = f"Database error: Invalid {fk_field} provided. Details: {error_detail}"
             else: msg = f"Database integrity error: {error_detail}"
         elif isinstance(e, DataError):
              # Often due to incorrect data type or length
              msg = f"Database data error: Invalid data format or type. Detail: {error_detail}"

         current_app.logger.error(f"Database error adding reason for rejection: {e}", exc_info=True)
         return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback() # Rollback on any other unexpected error
        current_app.logger.error(f"Unexpected error adding reason for rejection: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while adding the rejection record."}), 500


# <<< --- CONSOLIDATED PATCH ROUTE --- >>>
@reason_for_rejection_api.patch("/reason_for_rejection/<int:rejection_id>")
def update_rejection_record(rejection_id):
    """
    Updates a rejection record. Supports two modes based on form data:
    1. Admin Price Update: Requires 'admin_email' and 'price'. Updates only price
       and recalculates total_price. Logs against the original creator.
    2. Status/Comments Update: Requires 'user_email'. Updates 'status' and/or
       'comments'. Logs against the user identified by 'user_email'.

    If 'admin_email' and 'price' are provided and valid, Admin Price Update mode
    is triggered. Otherwise, if 'user_email' and ('status' or 'comments') are
    provided, User Status/Comments Update mode is triggered.
    Providing conflicting identifiers (e.g., both admin_email and user_email)
    or insufficient fields for either mode will result in an error.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    admin_email = request.form.get("admin_email")
    user_email = request.form.get("user_email")
    price_str = request.form.get("price")
    status_str = request.form.get("status") # Use get to handle absence
    comments_str = request.form.get("comments") # Use get to handle absence

    # --- Determine Mode ---
    # Admin Price Update mode conditions: admin_email AND price are present
    is_admin_price_update_mode = bool(admin_email and price_str is not None)
    # User Status/Comment Update mode conditions: user_email AND (status OR comments) are present
    is_user_update_mode = bool(user_email and (status_str is not None or comments_str is not None))

    # --- Validate Mode and Input Combinations ---
    if is_admin_price_update_mode and is_user_update_mode:
        # Disallow providing enough info for both modes simultaneously
        return jsonify(error={"message": "Cannot perform admin price update and user status/comment update simultaneously. Provide either ('admin_email' and 'price'), OR ('user_email' and ('status' or 'comments'))."}), 400
    elif is_admin_price_update_mode and user_email:
        # Disallow providing user_email when in admin mode
        return jsonify(error={"message": "Cannot provide 'user_email' when performing an admin price update (using 'admin_email' and 'price')."}), 400
    elif is_user_update_mode and admin_email:
         # Disallow providing admin_email when in user mode
         return jsonify(error={"message": "Cannot provide 'admin_email' when performing a user status/comment update (using 'user_email')."}), 400
    elif is_user_update_mode and price_str is not None:
        # Disallow providing price when in user mode
        return jsonify(error={"message": "Cannot provide 'price' when performing a user status/comment update (using 'user_email'). Use admin mode ('admin_email', 'price') to update price."}), 400
    elif is_admin_price_update_mode and (status_str is not None or comments_str is not None):
        # Disallow providing status/comments when in admin mode
        return jsonify(error={"message": "Cannot provide 'status' or 'comments' when performing an admin price update (using 'admin_email'). Use user mode ('user_email', 'status'/'comments') to update status/comments."}), 400
    elif not is_admin_price_update_mode and not is_user_update_mode:
        # Neither mode's conditions met, determine missing fields
        missing = []
        if admin_email and price_str is None: missing.append("'price' (required with 'admin_email')")
        if user_email and status_str is None and comments_str is None: missing.append("'status' or 'comments' (required with 'user_email')")
        if not admin_email and not user_email: missing.append("'admin_email' or 'user_email'")
        # If only price provided without admin_email
        if price_str is not None and not admin_email: missing.append("'admin_email' (required with 'price')")
        # If only status/comments provided without user_email
        if (status_str is not None or comments_str is not None) and not user_email: missing.append("'user_email' (required with 'status'/'comments')")

        error_msg = "Invalid request. Provide either ('admin_email' and 'price') for admin update, OR ('user_email' and ('status' or 'comments')) for user update."
        if missing:
            error_msg = f"Missing or invalid combination of required fields: {', '.join(missing)}."

        return jsonify(error={"message": error_msg}), 400

    # --- Get Rejection Record ---
    reason = db.session.get(ReasonForRejection, rejection_id)
    if not reason:
        return jsonify(message=f"Rejection record with ID {rejection_id} not found."), 404

    # --- Execute Based on Mode ---
    try:
        if is_admin_price_update_mode:
            # <<< --- ADMIN PRICE UPDATE LOGIC --- >>>
            current_app.logger.info(f"Processing admin price update for Rejection {rejection_id} by {admin_email}.")
            # Authorize Admin
            admin_user = AdminUser.query.filter(AdminUser.email.ilike(admin_email)).first()
            if not admin_user:
                current_app.logger.warning(f"Unauthorized PATCH price attempt on Rejection {rejection_id} by non-admin: {admin_email}")
                return jsonify(error={"message": "Access Denied. Admin privileges required or admin email not found."}), 403
            if admin_user.is_disabled:
                 current_app.logger.warning(f"Disabled admin {admin_email} attempted PATCH price on Rejection {rejection_id}.")
                 return jsonify(error={"message": "Access Denied. Administrator account is disabled."}), 403
            admin_login_id = admin_user.login_id

            # Find Original User for Logging
            creation_log = RejectionActivityLogs.query.filter(
                RejectionActivityLogs.rejection_id == rejection_id,
                RejectionActivityLogs.logs_description.like('Rejection record added%')
            ).order_by(RejectionActivityLogs.log_date.asc()).first()

            if not creation_log or creation_log.login_id is None:
                current_app.logger.error(f"CRITICAL: Could not find original user ID (via creation log) for Rejection {rejection_id}. Cannot log admin price update.")
                return jsonify(error={"message": "Inconsistent state: Could not determine original user for logging. Price update cancelled."}), 500
            original_user_id_for_log = creation_log.login_id
            current_app.logger.info(f"Admin price update for Rejection {rejection_id} will be logged against original user ID: {original_user_id_for_log}")

            # Validate and Update Price
            validation_errors = {}
            price_changed = False
            total_price_changed = False
            update_occurred = False
            original_price = reason.price
            original_total_price = reason.total_price

            try:
                new_price_float = float(price_str)
                if new_price_float < 0:
                    validation_errors["price"] = "Price cannot be negative."
                # Compare formatted prices to avoid float precision issues if possible
                elif format_price(new_price_float) != format_price(original_price):
                    reason.price = new_price_float
                    price_changed = True
                    update_occurred = True
            except (ValueError, TypeError):
                validation_errors["price"] = f"Invalid data type for price: '{price_str}'. Must be a number."

            if validation_errors:
                return jsonify(error={"message": "Validation failed during price update.", "details": validation_errors}), 400

            # Recalculate Total Price if price changed
            if price_changed:
                if reason.quantity is not None and reason.price is not None and reason.deduction_rate is not None:
                    try:
                        new_total_price = round(
                            float(reason.quantity) * float(reason.price) * (1.0 - (float(reason.deduction_rate) / 100.0)),
                            2
                        )
                        # Compare formatted prices
                        if format_price(new_total_price) != format_price(original_total_price):
                            reason.total_price = new_total_price
                            total_price_changed = True
                            update_occurred = True # Ensure this is true if total price changes even if price didn't (unlikely but possible with rounding)
                    except Exception as calc_e:
                        db.session.rollback()
                        current_app.logger.error(f"Error recalculating total_price for rejection {rejection_id} during PATCH by admin {admin_email}: Q={reason.quantity}, P={reason.price}, R={reason.deduction_rate}. Error: {calc_e}", exc_info=True)
                        return jsonify(error={"message": f"Failed to recalculate total price. Error: {calc_e}"}), 500
                else:
                     current_app.logger.warning(f"Cannot recalculate total_price for Rejection {rejection_id}: Missing quantity ({reason.quantity}), price ({reason.price}), or deduction_rate ({reason.deduction_rate}).")

            if not update_occurred:
                 current_app.logger.info(f"No effective change detected for Rejection {rejection_id} price/total_price update by admin {admin_email}.")
                 response_tuple = get_reason_for_rejection_by_id(rejection_id)
                 # ... (handle response tuple as before) ...
                 if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and response_tuple[1] == 200:
                      return jsonify(
                          message="No changes detected or applied to rejection price or total price.",
                          reason_for_rejection=response_tuple[0].json.get('reason_for_rejection')
                      ), 200
                 else:
                      return jsonify(message="No changes detected or applied."), 200

            # Log, Commit, Notify (using original_user_id_for_log)
            log_parts = []
            if price_changed: log_parts.append(f"price changed from {format_price(original_price)} to {format_price(reason.price)}")
            if total_price_changed: log_parts.append(f"total_price recalculated from {format_price(original_total_price)} to {format_price(reason.total_price)}")
            changes_str = '; '.join(log_parts) if log_parts else "No effective change"

            log_desc = (f"Rejection record (ID: {rejection_id}) price details updated by admin '{admin_email}' (Admin ID: {admin_login_id}). "
                        f"Changes: [{changes_str}].")

            update_log = log_rejection_activity(original_user_id_for_log, reason.rejection_id, log_desc)
            if not update_log:
                 db.session.rollback()
                 current_app.logger.error(f"Failed to log rejection price update activity (Rejection ID {rejection_id}) against original user ID {original_user_id_for_log}. Update transaction rolled back.")
                 return jsonify(error={"message": "Failed to create activity log against original user. Price update not saved."}), 500

            db.session.commit()
            db.session.refresh(reason)
            current_app.logger.info(f"Successfully updated Rejection {rejection_id} price via PATCH by admin {admin_email} (logged against original user ID {original_user_id_for_log}).")

            # Send Notifications (admin context)
            notify_payload = {
                "action": "update", "rejection_id": reason.rejection_id,
                "updated_by_admin": admin_email,
                "logged_against_user_id": original_user_id_for_log,
                "updated_fields": {},
                "status": reason.status, # Include current status
            }
            if price_changed: notify_payload["updated_fields"]["price"] = format_price(reason.price)
            if total_price_changed: notify_payload["updated_fields"]["total_price"] = format_price(reason.total_price)

            if notify_payload["updated_fields"]:
                send_notification('rejection_updates', notify_payload)
                send_notification('rejection_logs_updates', {
                    "action": "insert", "log_id": update_log.log_id,
                    "rejection_id": reason.rejection_id,
                    "user_id": original_user_id_for_log, # Logged against original user
                    "description": log_desc
                })

            # Success Response
            response_tuple = get_reason_for_rejection_by_id(rejection_id)
            # ... (handle response tuple robustly as before) ...
            if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and isinstance(response_tuple[0], Response):
                response_object = response_tuple[0]; status_code = response_tuple[1]
                if status_code == 200:
                    updated_reason_data = response_object.json.get('reason_for_rejection')
                    if updated_reason_data:
                        return jsonify(message=f"Rejection {rejection_id} price updated successfully by admin.", reason_for_rejection=updated_reason_data), 200
                    else: # Should not happen if GET works
                         current_app.logger.error(f"Failed to parse 'reason_for_rejection' key from internal GET after admin price PATCH.")
                         return jsonify(error={"message": "Price update successful, but failed to retrieve full updated record structure."}), 500
                else: # Internal GET failed
                    current_app.logger.error(f"Internal GET failed with status {status_code} after admin price PATCH.")
                    error_payload = response_object.json
                    return jsonify(error={"message": "Price update successful, but failed to retrieve full updated record.", "details": error_payload}), 500
            else: # Unexpected return from internal GET
                 current_app.logger.error(f"Unexpected return structure from internal GET after admin price PATCH: {response_tuple}")
                 return jsonify(error={"message": "Price update successful, but failed to retrieve full updated record due to internal response format error."}), 500


        elif is_user_update_mode:
            # <<< --- USER STATUS/COMMENTS UPDATE LOGIC --- >>>
            current_app.logger.info(f"Processing user status/comments update for Rejection {rejection_id} by {user_email}.")
            # Validate User
            user = Users.query.filter(Users.email.ilike(user_email)).first()
            if not user:
                return jsonify(error={"message": f"User with email '{user_email}' not found."}), 404
            if not user.isActive:
                return jsonify(error={"message": f"User '{user_email}' is not active."}), 403

            # Process Status/Comments Update
            updated_fields_log = []
            validation_errors = {}
            original_status = reason.status
            original_comments = reason.comments
            update_occurred = False

            # Update Status if provided
            if status_str is not None:
                new_status = status_str.strip()
                if new_status == "":
                    validation_errors['status'] = "Status cannot be empty if provided for update."
                elif new_status not in ALLOWED_REJECTION_STATUSES:
                    validation_errors['status'] = f"Invalid status '{new_status}'. Allowed: {', '.join(ALLOWED_REJECTION_STATUSES)}."
                elif new_status != reason.status:
                    reason.status = new_status
                    updated_fields_log.append(f"status changed from '{original_status}' to '{new_status}'")
                    update_occurred = True

            # Update Comments if provided
            if comments_str is not None:
                 new_comments = comments_str # Allow empty string
                 if new_comments != reason.comments:
                     reason.comments = new_comments
                     updated_fields_log.append("comments updated") # Avoid logging potentially long comments directly
                     update_occurred = True

            if validation_errors:
                return jsonify(error={"message": "Validation failed during update.", "details": validation_errors}), 400

            if not update_occurred:
                 current_app.logger.info(f"No effective change detected for Rejection {rejection_id} status/comments update by user {user_email}.")
                 response_tuple = get_reason_for_rejection_by_id(rejection_id)
                 # ... (handle response tuple as before) ...
                 if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and response_tuple[1] == 200:
                     return jsonify(
                         message="No changes detected or applied to status or comments.",
                         reason_for_rejection=response_tuple[0].json.get('reason_for_rejection')
                     ), 200
                 else:
                     return jsonify(message="No changes detected or applied."), 200

            # Log, Commit, Notify (using user.user_id)
            changes_str = '; '.join(updated_fields_log) if updated_fields_log else "No effective change"
            log_description = (f"Rejection record (ID: {rejection_id}) updated by user {user.first_name} {user.last_name} ({user.email}). "
                               f"Changes: [{changes_str}].")

            update_log = log_rejection_activity(user.user_id, rejection_id, log_description)
            if not update_log:
                 db.session.rollback()
                 current_app.logger.error(f"Failed to log rejection status/comments update activity (ID: {rejection_id}). Transaction rolled back.")
                 return jsonify(error={"message": "Failed to create activity log. Update not saved."}), 500

            db.session.commit()
            db.session.refresh(reason)
            current_app.logger.info(f"Successfully updated Rejection ID {rejection_id} status/comments by user {user.email}.")

            # Send Notifications (user context)
            notify_payload = {
                "action": "update", "rejection_id": rejection_id,
                "updated_by_user": user.email,
                "updated_fields": {},
                "status": reason.status, # Include current status
            }
            if reason.status != original_status: notify_payload["updated_fields"]["status"] = reason.status
            if reason.comments != original_comments: notify_payload["updated_fields"]["comments"] = reason.comments # Send updated comment

            if notify_payload["updated_fields"]:
                send_notification('rejection_updates', notify_payload)
                send_notification('rejection_logs_updates', {
                    "action": "insert", "log_id": update_log.log_id,
                    "rejection_id": rejection_id, "user_id": user.user_id,
                    "description": log_description
                })

            # Success Response
            response_tuple = get_reason_for_rejection_by_id(rejection_id)
            # ... (handle response tuple robustly as before) ...
            if isinstance(response_tuple, tuple) and len(response_tuple) == 2 and isinstance(response_tuple[0], Response):
                response_object = response_tuple[0]; status_code = response_tuple[1]
                if status_code == 200:
                    updated_reason_data = response_object.json.get('reason_for_rejection')
                    if updated_reason_data:
                         return jsonify(message=f"Rejection record {rejection_id} updated successfully.", reason_for_rejection=updated_reason_data), 200
                    else: # Should not happen
                         current_app.logger.error(f"Failed to parse 'reason_for_rejection' key from internal GET after user status/comment PATCH.")
                         return jsonify(error={"message": "Update successful, but failed to retrieve full updated record structure."}), 500
                else: # Internal GET failed
                    current_app.logger.error(f"Internal GET failed with status {status_code} after user status/comment PATCH.")
                    error_payload = response_object.json
                    return jsonify(error={"message": "Update successful, but failed to retrieve full updated record.", "details": error_payload}), 500
            else: # Unexpected return from internal GET
                 current_app.logger.error(f"Unexpected return structure from internal GET after user status/comment PATCH: {response_tuple}")
                 return jsonify(error={"message": "Update successful, but failed to retrieve full updated record due to internal response format error."}), 500

        # Note: The initial mode validation should prevent reaching here.
        else:
             current_app.logger.error(f"Reached unexpected state in PATCH /reason_for_rejection/{rejection_id}. No valid update mode triggered.")
             return jsonify(error={"message": "Internal server error: Could not determine update mode."}), 500

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        status_code = 400
        msg = f"Database error during update: {error_detail}"
        # Check specifically for FK violation during admin log attempt
        if is_admin_price_update_mode and 'original_user_id_for_log' in locals() and isinstance(e, IntegrityError) and 'rejection_activity_logs_login_id_fkey' in error_detail:
             msg = f"Database error logging price update against original user ID ({original_user_id_for_log}): {error_detail}. Ensure original user exists."
             status_code = 500 # Indicate internal data consistency issue
        current_app.logger.error(f"Database error updating rejection {rejection_id}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code

    except Exception as e:
        db.session.rollback()
        status_code = 500
        msg = "An unexpected internal server error occurred during the update."
        # Check specifically for error during admin's original user lookup
        if is_admin_price_update_mode and 'creation_log' not in locals() and isinstance(e, (AttributeError, TypeError)):
             msg = "An internal server error occurred while trying to find the original user for logging."
        current_app.logger.error(f"Unexpected error updating rejection {rejection_id}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code


# <<< --- ADMIN PRICE UPDATE ROUTE REMOVED --- >>>
# The functionality is now handled by the consolidated PATCH route above.
# @reason_for_rejection_api.patch("/reason_for_rejection/<int:rejection_id>/admin_price_update")
# def update_rejection_price_admin(rejection_id):
#     ... (Function removed) ...


# <<< --- DELETE ROUTE (NO EMAIL REQUIRED) --- >>>
@reason_for_rejection_api.delete("/reason_for_rejection/<int:rejection_id>")
def delete_reason_for_rejection(rejection_id):
    """
    Deletes a specific reason for rejection record by its ID.
    No user email is required in the form data. Logs to application logger only.
    Requires API Key for basic authorization.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        reason = db.session.get(ReasonForRejection, rejection_id)
        if not reason:
            return jsonify(message=f"Rejection ID {rejection_id} not found"), 404

        # Store details before deletion for logging/notification
        plant_name_ref = reason.plant_name; plant_id_ref = reason.plant_id; gh_id_ref = reason.greenhouse_id
        rejection_type_ref = reason.type

        log_desc = (f"Attempting deletion of Rejection record (ID: {rejection_id}, Type: {rejection_type_ref}, "
                    f"Plant: '{plant_name_ref}') via API request (no user context).")
        current_app.logger.info(log_desc)

        # Manually delete logs first to avoid potential FK issues if cascade isn't reliable
        num_logs_deleted = db.session.query(RejectionActivityLogs).filter(RejectionActivityLogs.rejection_id == rejection_id).delete(synchronize_session=False)
        if num_logs_deleted > 0:
             current_app.logger.info(f"Queued deletion of {num_logs_deleted} activity logs for Rejection ID {rejection_id}.")


        # Delete the main record
        db.session.delete(reason)
        db.session.commit()
        current_app.logger.info(f"Successfully committed deletion of rejection record {rejection_id} and {num_logs_deleted} associated logs.")

        # Send notification after successful commit
        send_notification('rejection_updates', {
            "action": "delete", "rejection_id": rejection_id,
            "gh_id": gh_id_ref, "plant_id": plant_id_ref
            # Cannot include deleted_by user details
        })

        return jsonify(message=f"Successfully deleted rejection record ID {rejection_id}"), 200

    except IntegrityError as e:
         db.session.rollback() # Rollback on integrity errors
         error_detail = str(getattr(e, 'orig', str(e)))
         current_app.logger.error(f"Integrity error deleting rejection {rejection_id}: {e}", exc_info=True)
         # Check if it's a foreign key constraint violation (e.g., if a Sale depends on this Rejection)
         msg = f"Cannot delete rejection record {rejection_id} due to database integrity constraints."
         if 'violates foreign key constraint' in error_detail.lower():
             # Try to identify the constraint if possible
             if 'sale' in error_detail.lower(): # Example check
                 msg = f"Cannot delete rejection record {rejection_id} because it is referenced by an existing Sale record."
             else:
                  msg = f"Cannot delete rejection record {rejection_id} because it is referenced by another record."
         return jsonify(error={"message": msg, "detail": error_detail}), 409 # Use 409 Conflict
    except Exception as e:
        db.session.rollback() # Rollback on any other unexpected error
        current_app.logger.error(f"Error deleting rejection record {rejection_id}: {e}", exc_info=True)
        detail = str(e)
        return jsonify(error={"message": "An internal server error occurred during deletion.", "detail": detail}), 500


# <<< --- NEW: DELETE ALL ROUTE (NO EMAIL REQUIRED) --- >>>
@reason_for_rejection_api.delete("/reason_for_rejection")
def delete_all_reasons_for_rejection():
    """
    Deletes ALL reason for rejection records and their associated logs.
    Requires confirmation parameter '?confirm=true'.
    No user identification required for this action beyond API Key.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error


    try:
        # Log the attempt before deletion
        current_app.logger.warning("Attempting bulk deletion of ALL reason_for_rejection records and their logs via API Key (Confirmation received).")

        # Delete associated logs first for safety/performance
        num_logs_deleted = db.session.query(RejectionActivityLogs).delete(synchronize_session=False)
        current_app.logger.info(f"Queued deletion of {num_logs_deleted} rejection activity logs.")

        # Delete all rejection records
        num_rejections_deleted = db.session.query(ReasonForRejection).delete(synchronize_session=False)
        current_app.logger.info(f"Queued deletion of {num_rejections_deleted} rejection records.")

        # Commit the transaction
        db.session.commit()
        log_msg = f"COMMITTED bulk deletion of {num_rejections_deleted} rejection records and {num_logs_deleted} associated logs."
        current_app.logger.warning(log_msg) # Keep as warning due to destructive nature

        # Send summary notification
        try:
            send_notification('rejection_updates', {
                "action": "delete_all",
                "rejections_deleted_count": num_rejections_deleted,
                "logs_deleted_count": num_logs_deleted,
                "deleted_by": "System/API Key" # Indicate it wasn't a specific user
            })
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send delete_all notification for rejections: {notify_e}", exc_info=True)

        return jsonify(
            message=f"Successfully deleted {num_rejections_deleted} rejection records and {num_logs_deleted} associated logs."
        ), 200

    except IntegrityError as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', str(e)))
        current_app.logger.error(f"Integrity error during bulk rejection deletion: {e}", exc_info=True)
        # Check if it's a foreign key constraint violation
        msg = "Cannot delete all rejection records due to database integrity constraints."
        if 'violates foreign key constraint' in error_detail.lower():
             msg = "Cannot delete all rejection records due to existing database references (e.g., Sales records potentially referencing them). Please remove dependent records first."
        return jsonify(error={"message": msg, "detail": error_detail}), 409 # Use 409 Conflict
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all rejection records: {e}", exc_info=True)
        return jsonify(error={"message": "An error occurred during bulk deletion."}), 500


# <<< --- GET BY DATE ROUTE --- >>>
@reason_for_rejection_api.get("/reason_for_rejection/date/<rejection_date_str>")
def get_reasons_for_rejection_by_date(rejection_date_str):
    """
    Gets reason for rejection records filtered by date (YYYY-MM-DD),
    including the name of the user associated with the creation log entry,
    and the rejection status.
    Does NOT include greenhouse_name.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        # Validate date format strictly
        rejection_date_obj = date.fromisoformat(rejection_date_str)
    except ValueError:
        return jsonify(error={"message": "Invalid date format. Use YYYY-MM-DD."}), 400
    try:
        # Query includes join to get user name from log
        query = db.session.query(
            ReasonForRejection,
            Users.first_name,
            Users.last_name
        ).select_from(ReasonForRejection).outerjoin(
            RejectionActivityLogs,
            (RejectionActivityLogs.rejection_id == ReasonForRejection.rejection_id) &
            (RejectionActivityLogs.logs_description.like('Rejection record added%')) # Match log description for creation
        ).outerjoin(
            Users, Users.user_id == RejectionActivityLogs.login_id
        ).options(
            # Eager load related PlantedCrops, but not Greenhouse
            db.joinedload(ReasonForRejection.planted_crops)
            # db.joinedload(ReasonForRejection.greenhouses) # Greenhouse name removed
        ).filter(
            # Use the date object for filtering
            ReasonForRejection.rejection_date == rejection_date_obj
        )

        # Order results meaningfully
        query_results = query.order_by(ReasonForRejection.greenhouse_id, ReasonForRejection.rejection_id).all()

        count = len(query_results) # Initial count based on query results
        message = f"Successfully retrieved {count} rejection record(s) for {rejection_date_str}"
        if count == 0:
            message = f"No rejection data found for {rejection_date_str}."

        response_data = []
        processed_ids = set() # Handle potential duplicate logs matching criteria
        for reason, first_name, last_name in query_results:
             if reason.rejection_id in processed_ids: continue # Skip duplicates
             processed_ids.add(reason.rejection_id)

             added_by_user_name = f"{first_name} {last_name}".strip() if first_name or last_name else "Unknown User"
             plant_name = reason.plant_name
             if not plant_name and reason.planted_crops:
                 plant_name = reason.planted_crops.plant_name

             response_data.append({
                "rejection_id": reason.rejection_id,
                "greenhouse_id": reason.greenhouse_id,
                # "greenhouse_name": reason.greenhouses.name if reason.greenhouses else None, # Removed
                "plant_id": reason.plant_id,
                "plant_name": plant_name,
                "name": added_by_user_name, # User who added the rejection
                "type": reason.type,
                "quantity": reason.quantity,
                "rejection_date": format_date(reason.rejection_date),
                "comments": reason.comments,
                "price": format_price(reason.price),
                "deduction_rate": format_price(reason.deduction_rate),
                "total_price": format_price(reason.total_price),
                "status": reason.status
            })

        # Recalculate count based on processed IDs
        final_count = len(response_data)
        message = f"Successfully retrieved {final_count} rejection record(s) for {rejection_date_str}" # Update message with final count
        if final_count == 0:
             message = f"No rejection data found for {rejection_date_str}."

        current_app.logger.info(f"GET /reason_for_rejection/date/{rejection_date_str}: {message}")
        return jsonify(message=message, count=final_count, reasons_for_rejection=response_data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching rejection records for date {rejection_date_str}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching rejection records by date."}), 500

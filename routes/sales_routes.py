# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\sales_routes.py
import os
from flask import Blueprint, request, jsonify, current_app
from db import db
# --- Model Imports ---
from models.sale_model import Sale
from models.harvest_model import Harvest # Needed to find harvest by ID
from models.reason_for_rejection_model import ReasonForRejection # Needed to find rejection by ID
from models.activity_logs.sale_activity_log_model import SaleLog
from models.users_model import Users
# PlantedCrops no longer directly needed for POST, but keep for GET if needed later
# from models.planted_crops_model import PlantedCrops
# --- End Model Imports ---
from datetime import datetime
import pytz
import psycopg2
import json
from sqlalchemy.exc import IntegrityError, DataError

sale_api = Blueprint("sale_api", __name__)

# --- Configuration ---
API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace") # Use a secure default or raise error
PH_TZ = pytz.timezone('Asia/Manila')
# Define allowed statuses for source items to be sold
ALLOWED_SOURCE_STATUS_FOR_SALE = ["Not Sold", "Processing"] # Add others if applicable

# --- Helper Functions ---
def check_api_key(request):
    """Checks if the provided API key in the header is valid."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect or missing api_key."}), 403
    return None

def send_sale_notification(payload):
    """Sends a notification to the 'sales_updates' channel."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error("Error: SQLALCHEMY_DATABASE_URI not configured.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
            curs.execute(f"NOTIFY sales_updates, %s;", (json.dumps(payload, default=str),))
        conn.close()
        current_app.logger.info(f"Sent notification to 'sales_updates': {payload}")
    except psycopg2.Error as e:
        current_app.logger.error(f"Error sending sale notification: {e}")
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred in send_sale_notification: {e}", exc_info=True)

def send_sale_logs_notification(payload):
    """Sends a notification to the 'sale_logs_updates' channel."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error("Error: SQLALCHEMY_DATABASE_URI not configured.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
            curs.execute(f"NOTIFY sale_logs_updates, %s;", (json.dumps(payload, default=str),))
        conn.close()
        current_app.logger.info(f"Sent notification to 'sale_logs_updates': {payload}")
    except psycopg2.Error as e:
        current_app.logger.error(f"Error sending sale activity log notification: {e}")
    except Exception as e:
        current_app.logger.error(f"An unexpected error occurred in send_sale_logs_notification: {e}", exc_info=True)

def format_datetime_ph(dt):
    """Helper to format datetime to PH time string (YYYY-MM-DD HH:MM:SS AM/PM)."""
    if not dt: return None
    # Ensure datetime is timezone-aware (assume UTC if naive)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt_aware = pytz.utc.localize(dt)
    else:
        dt_aware = dt.astimezone(pytz.utc)
    # Convert to Philippines Timezone
    dt_ph = dt_aware.astimezone(PH_TZ)
    return dt_ph.strftime("%Y-%m-%d %I:%M:%S %p")

def format_iso_datetime(dt):
    """Formats datetime objects consistently to ISO 8601 string (UTC)."""
    if dt is None: return None
    try:
        if isinstance(dt, datetime):
            if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
                dt_aware = pytz.utc.localize(dt) # Assume UTC if naive
            else:
                dt_aware = dt.astimezone(pytz.utc)
            return dt_aware.isoformat(timespec='seconds') # e.g., 2023-10-27T10:30:00+00:00
        else:
            return str(dt) # Fallback for non-datetime objects
    except Exception as e:
        current_app.logger.error(f"Error formatting datetime {dt} to ISO: {e}", exc_info=True)
        return str(dt)

# --- GET Endpoint ---
@sale_api.get("/sales")
def get_sales():
    """
    Retrieves all sales records, ordered by date descending.
    Formats the sales date to PH time with 'created_at' key.
    The 'name' field in the response represents the name of the user associated with the sale.
    (Using joinedload for efficiency as previously recommended)
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        # Fetch data using joinedload for efficiency
        sales_data = Sale.query.options(
            db.joinedload(Sale.users),
            db.joinedload(Sale.harvest),
            db.joinedload(Sale.reason_for_rejection)
        ).order_by(Sale.salesDate.desc()).all()

        if not sales_data:
            return jsonify(message="No sales data found.", sales=[]), 200

        sales_list = []
        for sale in sales_data:
            # Get the base dictionary from the model's helper
            sale_dict = sale.to_dict()

            # --- DATE FORMATTING AND KEY CHANGE ---
            formatted_ph_time = format_datetime_ph(sale.salesDate)
            sale_dict['created_at'] = formatted_ph_time
            if 'salesDate' in sale_dict:
                del sale_dict['salesDate']
            # --- END DATE FORMATTING ---

            # --- USER NAME/EMAIL ADJUSTMENT ---
            if 'user_name' in sale_dict:
                sale_dict['name'] = sale_dict['user_name']
                del sale_dict['user_name']
            else: # Fallback if to_dict() doesn't add user_name
               user_name_val = f"{sale.users.first_name} {sale.users.last_name}".strip() if sale.users else "Unknown User"
               sale_dict['name'] = user_name_val

            if 'user_email' in sale_dict:
                del sale_dict['user_email']
            # --- END USER NAME/EMAIL ADJUSTMENT ---

            sales_list.append(sale_dict)

        return jsonify(sales=sales_list), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching sales: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching sales."}), 500

# --- POST Endpoint ---
@sale_api.post("/sales")
def add_sale():
    """
    Adds a new sale record based on either a Harvest or a ReasonForRejection item.
    Requires 'user_email', 'currentPrice', 'quantity', and EITHER 'harvest_id' OR 'rejection_id'.
    Updates the status of the source Harvest/Rejection item to 'Sold'.
    Logs the action. Sends notifications.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error


    # --- Get data STRICTLY from request.form ---
    email = request.form.get("user_email")
    harvest_id_str = request.form.get("harvest_id")
    rejection_id_str = request.form.get("rejection_id")
    current_price_str = request.form.get("currentPrice")
    quantity_str = request.form.get("quantity")
    crop_description = request.form.get("cropDescription") # Optional

    # --- Basic Validation ---
    errors = {}
    if not email: errors['user_email'] = "Required."
    if not current_price_str: errors['currentPrice'] = "Required."
    if not quantity_str: errors['quantity'] = "Required."

    # Validate that EITHER harvest_id OR rejection_id is provided, but not both
    harvest_id = None
    rejection_id = None
    source_type = None

    if harvest_id_str and rejection_id_str:
        errors['source_id'] = "Provide either 'harvest_id' or 'rejection_id', not both."
    elif harvest_id_str:
        try:
            harvest_id = int(harvest_id_str)
            source_type = "Harvest"
        except (ValueError, TypeError):
            errors['harvest_id'] = "Must be a valid integer."
    elif rejection_id_str:
        try:
            rejection_id = int(rejection_id_str)
            source_type = "Rejection"
        except (ValueError, TypeError):
            errors['rejection_id'] = "Must be a valid integer."
    else:
        errors['source_id'] = "Either 'harvest_id' or 'rejection_id' is required."

    if errors:
        return jsonify(error={"message": "Missing or invalid required form fields.", "details": errors}), 400

    # --- Detailed Validation and Processing ---
    user = None
    source_item = None # Will hold the Harvest or ReasonForRejection object
    current_price = None
    quantity_sold = None
    total_price = None
    original_source_price = None # Store the price from the source item
    plant_name_from_source = None

    try:
        # Validate User
        user = Users.query.filter(Users.email.ilike(email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{email}' not found"}), 404
        if not user.isActive:
             return jsonify(error={"message": f"User '{email}' is not active."}), 403

        # Validate Numeric Inputs (Price, Quantity)
        try:
            current_price = float(current_price_str)
            quantity_sold = float(quantity_str) # Allow float for quantity (e.g., kg)
            if current_price < 0: errors['currentPrice'] = "Cannot be negative."
            if quantity_sold <= 0: errors['quantity'] = "Must be a positive number."
        except (ValueError, TypeError):
            errors['conversion'] = "Invalid data type for price or quantity."

        if errors:
            return jsonify(error={"message": "Data validation failed.", "details": errors}), 400

        # --- Fetch and Validate Source Item (Harvest or Rejection) ---
        if source_type == "Harvest":
            source_item = db.session.get(Harvest, harvest_id)
            if not source_item:
                return jsonify(error={"message": f"Harvest with ID {harvest_id} not found"}), 404
            # Check status
            if source_item.status not in ALLOWED_SOURCE_STATUS_FOR_SALE:
                return jsonify(error={"message": f"Harvest {harvest_id} cannot be sold. Current status: '{source_item.status}'"}), 409 # Conflict
            # Check quantity (sell exactly the accepted amount for now)
            if quantity_sold != source_item.accepted:
                 errors['quantity'] = f"Quantity ({quantity_sold}) must match the Harvest accepted quantity ({source_item.accepted}). Partial sales not currently supported by this logic."
                 # If partial sales ARE allowed, adjust logic here and don't error out.
                 # You'd need to potentially reduce Harvest.accepted or track remaining qty.
            original_source_price = source_item.price
            plant_name_from_source = source_item.plant_name

        elif source_type == "Rejection":
            source_item = db.session.get(ReasonForRejection, rejection_id)
            if not source_item:
                return jsonify(error={"message": f"Rejection record with ID {rejection_id} not found"}), 404
            # Check status
            if source_item.status not in ALLOWED_SOURCE_STATUS_FOR_SALE:
                 return jsonify(error={"message": f"Rejection {rejection_id} cannot be sold. Current status: '{source_item.status}'"}), 409 # Conflict
            # Check quantity (sell exactly the rejected amount for now)
            if quantity_sold != source_item.quantity:
                 errors['quantity'] = f"Quantity ({quantity_sold}) must match the Rejection quantity ({source_item.quantity}). Partial sales not currently supported by this logic."
            original_source_price = source_item.price # Use the rejection price as 'original'
            plant_name_from_source = source_item.plant_name

        if errors: # Re-check after quantity validation
            return jsonify(error={"message": "Data validation failed.", "details": errors}), 400

        # --- Update Source Item Status ---
        source_item.status = "Sold"
        db.session.add(source_item) # Add to session to track the update

        # --- Calculate Total Price for the Sale ---
        total_price = round(quantity_sold * current_price, 2)

        # --- Create New Sale Object ---
        new_sale = Sale(
            user_id=user.user_id,
            name=f"{user.first_name} {user.last_name}".strip(), # User's name
            harvest_id=harvest_id,        # Will be NULL if rejection_id is set
            rejection_id=rejection_id,    # Will be NULL if harvest_id is set
            plant_name=plant_name_from_source,
            originalPrice=original_source_price, # Price from source item
            currentPrice=current_price,          # Price from request
            quantity=quantity_sold,              # Quantity from request
            total_price=total_price,             # Calculated total
            cropDescription=crop_description     # Optional description
            # salesDate is handled by DB default
        )
        db.session.add(new_sale)
        db.session.flush() # Get the generated sale_id and default salesDate

        # --- Create Activity Log ---
        new_log = None
        log_msg = ""
        try:
            log_msg = (f"Sale created for {source_type} ID {source_item.rejection_id if source_type == 'Rejection' else source_item.harvest_id} "
                       f"(Plant: '{plant_name_from_source}'), Qty: {quantity_sold}, Total: {total_price:.2f}. "
                       f"Sale ID: {new_sale.sale_id}. User: {user.email}. "
                       f"{source_type} status updated to 'Sold'.")
            log_timestamp = datetime.now(pytz.utc) # Log timestamp should be UTC

            new_log = SaleLog(
                sale_id=new_sale.sale_id,
                login_id=user.user_id, # Store the user ID who performed the action
                log_message=log_msg,
                timestamp=log_timestamp
            )
            db.session.add(new_log)
            db.session.flush() # Get log_id if needed immediately
        except Exception as log_e:
            current_app.logger.error(f"Failed to create sale log for new sale ID {new_sale.sale_id}: {log_e}", exc_info=True)
            # Decide if logging failure should stop the whole process
            db.session.rollback() # Rollback if logging fails
            return jsonify(error={"message": "Failed to create activity log. Sale not completed."}), 500

        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(log_msg) # Log the success message

        # --- Trigger Notifications ---
        try:
            # Sale Update Notification
            sale_payload = new_sale.to_dict() # Use the model's helper
            sale_payload["action"] = "insert"
            sale_payload["user_email"] = user.email # Add user email if needed by listeners
            send_sale_notification(sale_payload)

            # Log Notification
            if new_log and new_log.log_id:
                log_payload = {
                    "action": "insert",
                    "log_id": new_log.log_id,
                    "sale_id": new_sale.sale_id,
                    "user_id": new_log.login_id,
                    "log_message": new_log.log_message,
                    "timestamp": format_iso_datetime(new_log.timestamp) # Use ISO format
                }
                send_sale_logs_notification(log_payload)

            # Source Item Status Update Notification
            if source_type == "Harvest":
                 # Assuming a 'harvests_updates' channel exists (similar to rejection_updates)
                 send_notification('harvests_updates', { # Use a generic send_notification if available
                     "action": "update",
                     "harvest_id": harvest_id,
                     "updated_fields": ["status"],
                     "status": "Sold",
                     "triggered_by_sale_id": new_sale.sale_id,
                     "last_updated": format_iso_datetime(source_item.last_updated) if hasattr(source_item, 'last_updated') else None
                 })
            elif source_type == "Rejection":
                 send_notification('rejection_updates', { # Use the existing rejection channel
                     "action": "update",
                     "rejection_id": rejection_id,
                     "updated_fields": ["status"],
                     "status": "Sold",
                     "triggered_by_sale_id": new_sale.sale_id
                     # Rejection model might not have last_updated, add if it does
                 })

        except NameError:
             current_app.logger.warning("Generic 'send_notification' function not found, skipping source update notifications.")
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send notifications for new sale {new_sale.sale_id}: {notify_e}", exc_info=True)
            # Don't rollback transaction just because notification failed

        # --- Prepare Success Response ---
        response_sale = new_sale.to_dict() # Use the helper again
        # Optionally add PH formatted date for display
        response_sale['salesDate_ph'] = format_datetime_ph(new_sale.salesDate)

        return jsonify(
            message=f"Sale added successfully. {source_type} ID {source_item.rejection_id if source_type == 'Rejection' else source_item.harvest_id} status updated to 'Sold'.",
            sale=response_sale
        ), 201

    # --- Error Handling ---
    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', e))
        status_code = 400
        msg = f"Database error: {error_detail}"
        if isinstance(e, IntegrityError):
            status_code = 409 # Conflict
            if 'chk_sale_source_exclusive' in error_detail:
                 msg = "Database Constraint Violation: Sale must link to either harvest_id OR rejection_id, not both or neither."
            elif 'violates foreign key constraint' in error_detail.lower():
                 msg = f"Database error: Invalid reference ID provided (user, harvest, or rejection). Details: {error_detail}"
            else: msg = f"Database integrity error: {error_detail}"
        elif isinstance(e, DataError): msg = f"Database data error: Invalid data format/type. Detail: {error_detail}"

        current_app.logger.error(f"Database error adding sale: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error adding sale: {e}", exc_info=True)
        return jsonify(error={"message": "An unexpected server error occurred while adding the sale."}), 500


# --- PATCH Endpoint ---
@sale_api.patch("/sales/<int:sale_id>")
def update_sale(sale_id):
    """
    Updates an existing sale record (e.g., price, quantity, description).
    Recalculates 'total_price' if 'currentPrice' or 'quantity' changes.
    Requires 'user_email' for logging. Does NOT change the linked harvest/rejection or status.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # --- Get user email for logging (Required for PATCH) ---
    email = request.form.get("user_email")
    if not email:
        return jsonify(error={"message": "Missing required form field for logging.", "details": {"user_email": "Required for auditing update."}}), 400

    # --- Find the user performing the update ---
    user = Users.query.filter(Users.email.ilike(email)).first()
    if not user:
        return jsonify(error={"message": f"User with email '{email}' not found. Cannot log update."}), 404

    # --- Find the sale to update ---
    sale = db.session.get(Sale, sale_id)
    if not sale:
        return jsonify(error={"message": f"Sale with ID {sale_id} not found."}), 404

    # --- Get potential updates from form data ---
    original_price_str = request.form.get("originalPrice") # Allow updating original price record? Maybe not.
    current_price_str = request.form.get("currentPrice")
    quantity_str = request.form.get("quantity")
    crop_description = request.form.get("cropDescription") # Optional, can be empty string

    updated_fields = {}
    errors = {}
    recalculate_total = False

    try:
        # --- Validate and process updates ---
        # Decide if originalPrice should be updatable post-creation. Usually not.
        # if original_price_str is not None and original_price_str != '': ...

        if current_price_str is not None and current_price_str != '':
            try:
                current_price = float(current_price_str)
                if current_price < 0:
                    errors['currentPrice'] = "Cannot be negative."
                else:
                    # Use Decimal for comparison if prices are stored as Decimal
                    # if sale.currentPrice != Decimal(current_price):
                    if sale.currentPrice != current_price: # Assuming float comparison is okay here
                        updated_fields['currentPrice'] = (sale.currentPrice, current_price)
                        sale.currentPrice = current_price
                        recalculate_total = True
            except (ValueError, TypeError):
                errors['currentPrice'] = "Invalid data type."

        if quantity_str is not None and quantity_str != '':
            try:
                quantity = float(quantity_str)
                if quantity <= 0:
                    errors['quantity'] = "Must be a positive number."
                else:
                     # Check against source item's available quantity if implementing partial sales later
                     # For now, assume quantity update might be for correction.
                     # if sale.quantity != Decimal(quantity):
                     if sale.quantity != quantity: # Assuming float comparison
                        # --- WARNING: If quantity changes, does it affect the source item? ---
                        # This logic assumes the sale quantity can be corrected independently.
                        # If changing sale quantity should revert source status or adjust source qty,
                        # complex logic is needed here. Sticking to simple sale record update for now.
                        current_app.logger.warning(f"Updating quantity for Sale ID {sale_id}. Ensure this doesn't require source item ({'H:'+str(sale.harvest_id) if sale.harvest_id else 'R:'+str(sale.rejection_id)}) adjustment.")
                        updated_fields['quantity'] = (sale.quantity, quantity)
                        sale.quantity = quantity
                        recalculate_total = True
            except (ValueError, TypeError):
                errors['quantity'] = "Invalid data type."

        # Update description if provided
        if crop_description is not None:
            if sale.cropDescription != crop_description:
                updated_fields['cropDescription'] = (sale.cropDescription, crop_description)
                sale.cropDescription = crop_description

        if errors:
            return jsonify(error={"message": "Data validation failed.", "details": errors}), 400

        # --- Check if any updates were actually made ---
        if not updated_fields and not recalculate_total: # Need recalculate flag in case only total price changes due to float precision
             # Fetch current state to return
             current_sale_data = sale.to_dict()
             current_sale_data['salesDate_ph'] = format_datetime_ph(sale.salesDate)
             return jsonify(message="No changes detected. Sale not updated.", sale=current_sale_data), 200

        # --- Recalculate total price if needed ---
        original_total_price = sale.total_price
        if recalculate_total:
            new_total_price = round(sale.quantity * sale.currentPrice, 2)
            # if sale.total_price != Decimal(new_total_price):
            if sale.total_price != new_total_price: # Assuming float comparison
                updated_fields['total_price'] = (original_total_price, new_total_price)
                sale.total_price = new_total_price
        elif 'total_price' not in updated_fields and sale.total_price != round(sale.quantity * sale.currentPrice, 2):
             # Handle cases where float precision might cause a mismatch even if inputs didn't change
             new_total_price = round(sale.quantity * sale.currentPrice, 2)
             updated_fields['total_price'] = (original_total_price, new_total_price)
             sale.total_price = new_total_price


        # --- Create Activity Log ---
        new_log = None
        log_msg = ""
        try:
            # Format changes for logging
            change_details = []
            for k, (ov, nv) in updated_fields.items():
                 ov_fmt = f"'{ov}'" if isinstance(ov, str) else ov
                 nv_fmt = f"'{nv}'" if isinstance(nv, str) else nv
                 change_details.append(f"{k}: {ov_fmt} -> {nv_fmt}")
            changes_str = "; ".join(change_details)

            log_msg = (f"Sale ID {sale_id} updated by User '{user.email}'. "
                       f"Changes: [{changes_str}].")
            log_timestamp = datetime.now(pytz.utc)

            new_log = SaleLog(
                sale_id=sale.sale_id,
                login_id=user.user_id, # User who performed the update
                log_message=log_msg,
                timestamp=log_timestamp
            )
            db.session.add(new_log)
            db.session.flush()
        except Exception as log_e:
            current_app.logger.error(f"Failed to create sale log for updated sale ID {sale_id}: {log_e}", exc_info=True)
            db.session.rollback() # Rollback if logging fails
            return jsonify(error={"message": "Failed to log update. Sale not updated."}), 500

        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(log_msg) # Log the update details

        # --- Trigger Notifications ---
        try:
            sale_payload = sale.to_dict()
            sale_payload["action"] = "update"
            sale_payload["user_email"] = user.email # Identify updater
            sale_payload["updated_fields"] = list(updated_fields.keys()) # Send list of changed fields
            send_sale_notification(sale_payload)

            if new_log and new_log.log_id:
                log_payload = {
                    "action": "insert", # Log is still an insert event
                    "log_id": new_log.log_id,
                    "sale_id": sale.sale_id,
                    "user_id": new_log.login_id,
                    "log_message": new_log.log_message,
                    "timestamp": format_iso_datetime(new_log.timestamp)
                }
                send_sale_logs_notification(log_payload)
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send notifications for updated sale {sale_id}: {notify_e}", exc_info=True)

        # --- Prepare Success Response ---
        response_sale = sale.to_dict()
        response_sale['salesDate_ph'] = format_datetime_ph(sale.salesDate) # Add formatted date

        return jsonify(message=f"Sale ID {sale_id} updated successfully.", sale=response_sale), 200

    # --- Error Handling ---
    except (IntegrityError, DataError) as e:
        db.session.rollback()
        error_detail = str(getattr(e, 'orig', e))
        status_code = 400 # Bad Request or Conflict?
        msg = f"Database error during update: {error_detail}"
        current_app.logger.error(f"Database error updating sale {sale_id}: {e}", exc_info=True)
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error updating sale {sale_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An unexpected server error occurred while updating the sale."}), 500


# --- DELETE Endpoints ---

@sale_api.delete("/sales/<int:sale_id>")
def delete_sale(sale_id):
    """
    Deletes a specific sale record by its ID and associated logs.
    Does NOT automatically revert the status of the source Harvest/Rejection item.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # Optional: Require user email for logging who deleted it
    # email = request.args.get("user_email") ... find user ...
    # user = Users.query.filter(Users.email.ilike(email)).first() if email else None
    # deleter_user_id = user.user_id if user else None

    try:
        sale = db.session.get(Sale, sale_id)
        if not sale:
            return jsonify(error={"message": f"Sale with ID {sale_id} not found."}), 404

        # Store details before deletion
        deleted_sale_id = sale.sale_id
        deleted_plant_name = sale.plant_name
        source_id_str = f"H:{sale.harvest_id}" if sale.harvest_id else f"R:{sale.rejection_id}"
        original_user_id = sale.user_id # User who originally made the sale

        # --- WARNING: Status Reversal ---
        # Deleting a sale might imply the source item is no longer "Sold".
        # Add logic here to find the source Harvest/Rejection and revert its status
        # back to "Not Sold" or "Processing" if required by business rules.
        # This requires careful consideration of edge cases (e.g., was it sold again later?).
        # For now, deletion only removes the sale record.
        current_app.logger.warning(f"Deleting Sale ID {sale_id} for source {source_id_str}. Status of the source item is NOT automatically reverted by this operation.")

        # The cascade="all, delete-orphan" on Sale.sale_logs should handle log deletion.
        # If cascade isn't working or not desired, delete logs manually:
        # logs_deleted_count = SaleLog.query.filter_by(sale_id=sale_id).delete(synchronize_session='fetch')

        # Delete the Sale
        db.session.delete(sale)
        log_msg = f"Queued deletion for Sale ID: {sale_id} (Source: {source_id_str}, Plant: {deleted_plant_name}, Original UserID: {original_user_id})."
        # If tracking deleter: log_msg += f" Deleted by UserID: {deleter_user_id}."
        current_app.logger.info(log_msg)

        # Commit
        db.session.commit()
        current_app.logger.info(f"Successfully committed deletion of Sale ID {deleted_sale_id}.") # Removed log count as cascade handles it

        # Send Notification
        try:
            send_sale_notification({
                "action": "delete",
                "sale_id": deleted_sale_id,
                "source_id": source_id_str, # Indicate which source was involved
                "plant_name": deleted_plant_name,
                "original_user_id": original_user_id,
                # "deleted_by_user_id": deleter_user_id # If tracking who deleted
            })
            # Log deletion notification?
            # send_sale_logs_notification({... 'action': 'delete_logs_for_sale', ...})
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send delete notification for sale {deleted_sale_id}: {notify_e}", exc_info=True)

        return jsonify(message=f"Sale ID {sale_id} (Source: {source_id_str}) deleted successfully."), 200 # Removed log count

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Integrity error deleting sale {sale_id}: {e}", exc_info=True)
        error_detail = str(getattr(e, 'orig', e))
        # Check if it's a FK constraint preventing deletion (shouldn't happen with cascade/SET NULL)
        return jsonify(error={"message": f"Cannot delete sale {sale_id} due to database constraints.", "detail": error_detail}), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting sale {sale_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An unexpected server error occurred during deletion."}), 500


@sale_api.delete("/sales")
def delete_all_sales():
    """
    Deletes ALL sale records and their associated logs. Requires confirmation.
    No user identification required for this action.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error



    # --- User email check removed ---
    # Optional: Log the IP or some other identifier if needed for auditing
    # request_ip = request.remote_addr
    # current_app.logger.info(f"Bulk sale deletion requested by {request_ip}")

    try:
        # Cascade should handle logs. If not, delete logs first.
        # num_logs_deleted = SaleLog.query.delete(synchronize_session=False)

        # Delete sales
        num_sales_deleted = Sale.query.delete(synchronize_session=False)
        current_app.logger.info(f"Queued bulk deletion for {num_sales_deleted} total sale entries.")

        # Commit
        db.session.commit()
        log_msg = f"COMMITTED bulk deletion of {num_sales_deleted} sales (and associated logs via cascade)."
        current_app.logger.warning(log_msg) # Keep as warning due to destructive nature

        # Send summary notification
        try:
            send_sale_notification({
                "action": "delete_all",
                "sales_deleted_count": num_sales_deleted,
                # "logs_deleted_count": num_logs_deleted # If manually deleted
                # "deleted_by": "System/API Key" # Indicate it wasn't a specific user
            })
        except Exception as notify_e:
            current_app.logger.error(f"Failed to send delete_all notification for sales: {notify_e}", exc_info=True)

        return jsonify(
            message=f"Successfully deleted {num_sales_deleted} sale records and associated logs."
        ), 200

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Integrity error during bulk sale deletion: {e}", exc_info=True)
        error_detail = str(getattr(e, 'orig', e))
        return jsonify(error={"message": "Cannot delete all sales due to existing database references.", "detail": error_detail}), 409
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all sales: {e}", exc_info=True)
        return jsonify(error={"message": "An error occurred during bulk deletion."}), 500

# --- Add a generic send_notification function if needed by Harvest/Rejection ---
# This function might already exist elsewhere in your project
def send_notification(channel, payload):
    """Generic notification sender."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error(f"DB URI not configured for channel {channel}.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
            # Ensure channel name is safe (basic validation)
            if not channel.isalnum() and '_' not in channel:
                 current_app.logger.error(f"Invalid channel name attempted: {channel}")
                 return
            curs.execute(f"NOTIFY {channel}, %s;", (json.dumps(payload, default=str),))
        conn.close()
        current_app.logger.info(f"Sent notification to channel '{channel}': {payload}")
    except psycopg2.Error as e:
        current_app.logger.error(f"Database error sending notification to {channel}: {e}")
    except Exception as e:
        current_app.logger.error(f"Unexpected error sending notification to {channel}: {e}", exc_info=True)

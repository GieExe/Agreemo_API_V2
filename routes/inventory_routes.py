# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\inventory_routes.py
import os
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import pytz
from db import db
from models.inventory_model import Inventory, InventoryContainer
# Correct import path for logs as per your structure
from models.activity_logs.inventory_container_activity_logs import InventoryContainerLog
from models.activity_logs.inventory_log_model import InventoryLog
# Correct imports needed for User/Greenhouse lookup
from models.greenhouses_model import Greenhouse
from models.users_model import Users
# Import for DB specific errors if needed
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy import func # Import func for case-insensitive comparison if needed
import psycopg2 # For sending NOTIFY commands
import json # For formatting notification payload

inventory_api = Blueprint('inventory_api', __name__)

# Load API Key from environment or use a default (replace default in production)
API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace")
# Set timezone to Philippines Time
PH_TZ = pytz.timezone('Asia/Manila')

# Define types that correspond to InventoryContainer fields
CONTAINER_ITEM_TYPES = ["ph_up", "ph_down", "solution_a", "solution_b"]


# --- Helper Functions ---

def format_datetime(dt):
    """Formats a datetime object to Philippines time string (YYYY-MM-DD hh:mm:ss AM/PM) or returns None."""
    if not dt or not isinstance(dt, datetime):
        return None
    try:
        dt_aware = None
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            # Assume naive datetime IS PH time if coming from DB default NOW() in PH
            dt_aware = PH_TZ.localize(dt)
            # If you know naive is UTC, use:
            # dt_aware = pytz.utc.localize(dt).astimezone(PH_TZ)
        else:
            dt_aware = dt.astimezone(PH_TZ)
        return dt_aware.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        current_app.logger.warning(f"Could not format datetime {dt} to PH time format: {e}. Falling back.")
        try:
            return dt.isoformat()
        except:
            return str(dt)

def send_notification(channel, payload):
    """Sends a notification payload to a specified PostgreSQL NOTIFY channel."""
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        current_app.logger.error(f"SQLALCHEMY_DATABASE_URI not configured for channel {channel}.")
        return
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
            # Use default=str to handle potential non-serializable types like Decimal or datetime
            curs.execute(f"NOTIFY {channel}, %s;", (json.dumps(payload, default=str),))
        conn.close()
        current_app.logger.info(f"Sent notification to channel '{channel}': {payload}")
    except psycopg2.Error as e:
        current_app.logger.error(f"DB error sending notification to {channel}: {e}")
    except Exception as e:
        current_app.logger.error(f"Unexpected error sending notification to {channel}: {e}", exc_info=True)


# *** Logging function for InventoryLog ***
def log_inventory_change(inventory_id, user_id, change_type, description):
    """
    Logs a change related to the main Inventory item using the InventoryLog model.
    Returns the log object or None on failure.
    """
    if inventory_id is None or user_id is None:
        current_app.logger.error(f"Attempted InventoryLog with missing inventory_id ({inventory_id}) or user_id ({user_id})")
        return None
    try:
        inventory_log = InventoryLog(
            inventory_id=inventory_id,
            user_id=user_id,
            change_type=change_type,
            description=description
            # timestamp uses DB default
        )
        db.session.add(inventory_log)
        db.session.flush() # Get log_id if needed immediately
        current_app.logger.info(f"Prepared InventoryLog entry (ID: {inventory_log.log_id}) for inventory_id {inventory_id}")
        return inventory_log
    except Exception as e:
        db.session.rollback() # Rollback on logging error
        current_app.logger.error(f"Error preparing InventoryLog for inventory_id {inventory_id}: {e}", exc_info=True)
        return None # Indicate failure

# *** Logging function for InventoryContainerLog ***
def log_container_change(container_id, user_id, item, old_quantity, new_quantity, description, change_type):
    """
    Logs a change to the InventoryContainerLog table.
    Returns the log object or None on failure.
    """
    if container_id is None or user_id is None or not change_type:
         current_app.logger.error(f"Attempted InventoryContainerLog with missing container_id ({container_id}), user_id ({user_id}), or change_type ({change_type})")
         return None
    try:
        container_log = InventoryContainerLog(
            inventory_container_id=container_id,
            user_id=user_id, # User performing the action
            change_type=change_type, # Assign the change type
            item=item, # e.g., "ph_up", "solution_a"
            old_quantity=int(old_quantity) if old_quantity is not None else 0, # Ensure integer
            new_quantity=int(new_quantity) if new_quantity is not None else 0, # Ensure integer
            description=description
            # timestamp uses DB default
        )
        db.session.add(container_log)
        db.session.flush() # Get log_id if needed
        current_app.logger.info(f"Prepared InventoryContainerLog (ID: {container_log.log_id}) for container {container_id}, item {item}, user_id {user_id}, type {change_type}")
        return container_log
    except Exception as e:
        db.session.rollback() # Rollback on logging error
        current_app.logger.error(f"Error preparing InventoryContainerLog for container {container_id}: {e}", exc_info=True)
        return None # Indicate failure


# Helper function to check API key
def check_api_key(request):
    """Checks if the provided API key in the header is valid."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        current_app.logger.warning(f"Unauthorized API attempt with key: {api_key_header}")
        return jsonify(
            error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403
    return None


# --- Inventory Item Routes ---

@inventory_api.route('/inventory', methods=['GET'])
def get_all_inventory_records():
    """Retrieve all inventory item records, optionally filtered by greenhouse_id."""
    api_key_error = check_api_key(request)
    if api_key_error:
        return api_key_error

    try:
        greenhouse_id_filter = request.args.get('greenhouse_id', type=int)
        query = Inventory.query
        if greenhouse_id_filter:
            query = query.filter(Inventory.greenhouse_id == greenhouse_id_filter)

        records = query.order_by(Inventory.greenhouse_id, Inventory.item_name).all()

        records_list = []
        for record in records:
            # Safely convert numeric types for JSON response
            quantity_val = int(record.quantity) if record.quantity is not None else 0
            total_price_val = float(record.total_price) if record.total_price is not None else 0.0
            max_total_ml_val = float(record.max_total_ml) if record.max_total_ml is not None else 0.0
            price_val = float(record.price) if record.price is not None else 0.0

            record_data = {
                "inventory_id": record.inventory_id,
                "inventory_container_id": record.inventory_container_id, # Include link if needed
                "greenhouse_id": record.greenhouse_id,
                "item_name": record.item_name,
                "user_name": record.user_name, # Name of user who added the record
                "type": record.type,
                "quantity": quantity_val,
                "total_price": total_price_val,
                "max_total_ml": max_total_ml_val,
                "created_at": format_datetime(record.created_at),
                "price": price_val,
            }
            records_list.append(record_data)

        log_msg = f"Fetched {len(records_list)} inventory records"
        if greenhouse_id_filter:
             log_msg += f" for greenhouse {greenhouse_id_filter}"
        current_app.logger.info(log_msg)

        return jsonify(
            message=f"Found {len(records_list)} inventory records." if records_list else "No inventory records found.",
            count=len(records_list),
            inventory_records=records_list
        ), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching all inventory records: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching inventory records."}), 500


@inventory_api.get("/inventory/<int:inventory_id>")
def get_inventory_record(inventory_id):
    """Gets a specific inventory item record by its ID."""
    api_key_error = check_api_key(request)
    if api_key_error:
        return api_key_error

    try:
        record = db.session.get(Inventory, inventory_id)
        if not record:
            current_app.logger.warning(f"Inventory record {inventory_id} not found")
            return jsonify(error={"message": "Inventory record not found"}), 404

        # Safely convert numeric types
        quantity_val = int(record.quantity) if record.quantity is not None else 0
        total_price_val = float(record.total_price) if record.total_price is not None else 0.0
        max_total_ml_val = float(record.max_total_ml) if record.max_total_ml is not None else 0.0
        price_val = float(record.price) if record.price is not None else 0.0

        record_data = {
            "inventory_id": record.inventory_id,
            "inventory_container_id": record.inventory_container_id,
            "greenhouse_id": record.greenhouse_id,
            "item_name": record.item_name,
            "user_name": record.user_name,
            "type": record.type,
            "quantity": quantity_val,
            "total_price": total_price_val,
            "max_total_ml": max_total_ml_val,
            "created_at": format_datetime(record.created_at),
            "price": price_val,
        }

        current_app.logger.info(f"Fetched inventory record: {record.inventory_id}")
        return jsonify(inventory_record=record_data), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching inventory record {inventory_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred while fetching the inventory record."}), 500


@inventory_api.post("/inventory")
def add_inventory_record():
    """
    Adds a new inventory item record (e.g., a purchase).
    Requires: greenhouse_id, item_name, type, quantity, price, email (of creator).
    Optional: max_total_ml (size of container purchased).
    If type matches a container item (ph_up, etc.), it INCREMENTS the corresponding
    field in the greenhouse's InventoryContainer by the 'quantity' added.
    Logs creation events.
    """
    api_key_error = check_api_key(request)
    if api_key_error:
        return api_key_error

    try:
        # --- Get Data from Form ---
        form_data = request.form
        greenhouse_id = form_data.get("greenhouse_id", type=int)
        item_name = form_data.get("item_name")
        inventory_type = form_data.get("type") # This type determines if it affects a container
        quantity_str = form_data.get("quantity") # Quantity of this item being added/purchased
        price_str = form_data.get("price") # Price per unit/item purchased
        email = form_data.get("email") # Email of user adding the record
        max_total_ml_str = form_data.get("max_total_ml") # Optional: Size of container/package purchased

        # --- Validation ---
        errors = {}
        quantity = None
        price = None
        max_total_ml = 0.0 # Default if not provided

        if not greenhouse_id: errors["greenhouse_id"] = "Required and must be an integer."
        if not item_name or not item_name.strip(): errors["item_name"] = "Required."
        if not inventory_type or not inventory_type.strip(): errors["type"] = "Required."
        if not email or not email.strip(): errors["email"] = "User email is required."

        try:
            if quantity_str is None: errors["quantity"] = "Required."
            else:
                quantity = int(quantity_str)
                if quantity <= 0: errors["quantity"] = "Must be positive." # Typically adding stock
        except (ValueError, TypeError): errors["quantity"] = "Must be a valid integer."

        try:
            if price_str is None: errors["price"] = "Required."
            else:
                price = float(price_str)
                if price < 0: errors["price"] = "Cannot be negative."
        except (ValueError, TypeError): errors["price"] = "Must be a valid number."

        if max_total_ml_str is not None and max_total_ml_str.strip() != '':
            try:
                max_total_ml = float(max_total_ml_str)
                if max_total_ml < 0: errors["max_total_ml"] = "Cannot be negative."
            except (ValueError, TypeError): errors["max_total_ml"] = "Must be a valid number."

        if errors:
            return jsonify(error={"message": "Validation failed", "errors": errors}), 400

        # --- Validate Greenhouse and User ---
        greenhouse = db.session.get(Greenhouse, greenhouse_id)
        if not greenhouse:
            return jsonify(error={"message": f"Greenhouse with ID {greenhouse_id} not found"}), 404

        creator_user = Users.query.filter(func.lower(Users.email) == func.lower(email)).first()
        if not creator_user:
            return jsonify(error={"message": f"User with email '{email}' not found"}), 404
        creator_full_name = f"{creator_user.first_name} {creator_user.last_name}".strip()
        creator_user_id = creator_user.user_id

        # --- Create New Inventory Record ---
        # total_price represents the value of this specific inventory addition/purchase
        total_price = quantity * price
        new_record = Inventory(
            greenhouse_id=greenhouse_id,
            item_name=item_name.strip(),
            user_name=creator_full_name, # User who added this record
            type=inventory_type.strip(),
            quantity=quantity, # Quantity of this specific addition
            total_price=total_price,
            price=price,
            max_total_ml=max_total_ml, # Size of bottle/package
            # created_at uses DB default
            # inventory_container_id is set below if applicable
        )
        db.session.add(new_record)
        db.session.flush() # Get the new_record.inventory_id

        if new_record.inventory_id is None:
             db.session.rollback()
             current_app.logger.error("CRITICAL: Inventory ID is None after flush.")
             return jsonify(error={"message": "Internal server error: Failed to generate inventory ID."}), 500

        # --- Container Update Logic ---
        container_field = None
        if inventory_type.strip().lower() in CONTAINER_ITEM_TYPES:
            container_field = inventory_type.strip().lower() # e.g., "ph_up"

        inventory_container = None
        container_log = None
        if container_field:
            # Find or create the container for this greenhouse
            inventory_container = InventoryContainer.query.filter_by(
                greenhouse_id=greenhouse_id
            ).with_for_update().first() # Lock the container row

            if not inventory_container:
                 # Create if not exists
                 current_app.logger.info(f"Creating new InventoryContainer for greenhouse {greenhouse_id} triggered by inventory item {new_record.inventory_id}")
                 inventory_container = InventoryContainer(greenhouse_id=greenhouse_id)
                 db.session.add(inventory_container)
                 db.session.flush() # Get the new container ID
                 current_app.logger.info(f"New container created (ID: {inventory_container.inventory_container_id}) for greenhouse {greenhouse_id}.")
                 # Log container creation separately if needed (or combine with update log)


            # Link the inventory item to the container
            new_record.inventory_container_id = inventory_container.inventory_container_id

            # Increment the container level
            old_level = getattr(inventory_container, container_field, 0)
            new_level = old_level + quantity # Add the quantity purchased
            setattr(inventory_container, container_field, new_level)
            db.session.add(inventory_container) # Add updated container to session

            # Log the container level change
            container_log_desc = f"Container level '{container_field}' increased by {quantity} (from {old_level} to {new_level}) due to addition of inventory item '{item_name}' (ID: {new_record.inventory_id}) by {creator_user.email}."
            container_log = log_container_change(
                container_id=inventory_container.inventory_container_id,
                user_id=creator_user_id,
                item=container_field,
                old_quantity=old_level,
                new_quantity=new_level,
                description=container_log_desc,
                change_type="add_stock" # Specific change type
            )
            if not container_log: # Handle logging failure
                db.session.rollback()
                current_app.logger.error(f"Failed to log container change for inventory add (Inv ID {new_record.inventory_id}). Transaction rolled back.")
                return jsonify(error={"message": "Failed to create container activity log. Inventory not added."}), 500


        # --- Log Inventory Record Creation ---
        log_description = (f"Created inventory item '{new_record.item_name}' (ID: {new_record.inventory_id}, Type: {new_record.type}), "
                           f"Qty: {new_record.quantity}, Price: {new_record.price:.2f}, "
                           f"Max ML: {new_record.max_total_ml:.1f} by user {creator_user.email}.")
        inventory_log = log_inventory_change(
            inventory_id=new_record.inventory_id,
            user_id=creator_user_id,
            change_type="create",
            description=log_description
        )
        if not inventory_log: # Handle logging failure
            db.session.rollback()
            current_app.logger.error(f"Failed to log inventory creation (Inv ID {new_record.inventory_id}). Transaction rolled back.")
            return jsonify(error={"message": "Failed to create inventory activity log. Inventory not added."}), 500

        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(f"Inventory transaction committed for new item '{item_name}' (ID: {new_record.inventory_id}), greenhouse {greenhouse_id}.")

        # --- Prepare and Return Response ---
        response_data = {
            "inventory_id": new_record.inventory_id,
            "inventory_container_id": new_record.inventory_container_id,
            "greenhouse_id": new_record.greenhouse_id,
            "item_name": new_record.item_name,
            "user_name": new_record.user_name,
            "type": new_record.type,
            "quantity": int(new_record.quantity),
            "total_price": float(new_record.total_price),
            "max_total_ml": float(new_record.max_total_ml),
            "created_at": format_datetime(new_record.created_at),
            "price": float(new_record.price),
        }
        # Add container info if updated
        if inventory_container:
             response_data["updated_container"] = {
                 "inventory_container_id": inventory_container.inventory_container_id,
                 container_field: getattr(inventory_container, container_field) # Show new level
             }

        # Send Notifications
        send_notification('inventory_updates', {"action": "insert", "inventory": response_data})
        if container_log:
             send_notification('inventory_container_logs_updates', {"action": "insert", "log_id": container_log.log_id, "container_id": container_log.inventory_container_id, "user_id": creator_user_id})
        send_notification('inventory_logs_updates', {"action": "insert", "log_id": inventory_log.log_id, "inventory_id": inventory_log.inventory_id, "user_id": creator_user_id})


        return jsonify(message="Inventory record added successfully", inventory=response_data), 201

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        current_app.logger.error(f"Database error adding inventory record: {e}", exc_info=True)
        orig_error = str(getattr(e, 'orig', e))
        status_code = 400
        msg = f"Database error: {orig_error}"
        if isinstance(e, IntegrityError): status_code = 409 # Conflict
        elif isinstance(e, DataError): msg = f"Invalid data format: {orig_error}"
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error adding inventory record: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# --- PATCH Endpoint (For correcting inventory item details) ---
@inventory_api.patch("/inventory/<int:inventory_id>")
def update_inventory_record(inventory_id):
    """
    Partially updates an inventory item record (e.g., correcting quantity purchased,
    price, or max_total_ml of the package).
    Requires email of the updater for logging.
    Recalculates total_price based on updated quantity and price.
    NOTE: This does NOT update the InventoryContainer levels. Use a separate
          endpoint for recording usage or adjustments.
    """
    api_key_error = check_api_key(request)
    if api_key_error:
        return api_key_error

    try:
        updater_email = request.form.get("email")
        if not updater_email or not updater_email.strip():
             return jsonify(error={"message": "Updater email is required for logging."}), 400

        updater_user = Users.query.filter(func.lower(Users.email) == func.lower(updater_email)).first()
        if not updater_user:
            return jsonify(error={"message": f"User with email '{updater_email}' not found."}), 404
        updater_user_id = updater_user.user_id

        record = db.session.get(Inventory, inventory_id)
        if not record:
            return jsonify(error={"message": "Inventory record not found"}), 404

        form_data = request.form
        updated_fields = []
        log_details = []
        validation_errors = {}
        quantity_updated = False
        price_updated = False
        update_occurred = False # Flag if any field actually changes

        original_quantity = record.quantity
        original_price = record.price
        original_max_ml = record.max_total_ml
        original_total_price = record.total_price

        # Validate and update quantity (of this specific purchase/item)
        if "quantity" in form_data:
            new_quantity_str = form_data.get("quantity")
            try:
                if new_quantity_str is None or new_quantity_str.strip() == '': raise ValueError("cannot be empty")
                new_val = int(new_quantity_str)
                if new_val <= 0: raise ValueError("must be positive") # Usually correcting a purchase qty
                if record.quantity != new_val:
                    record.quantity = new_val
                    quantity_updated = True
                    updated_fields.append("quantity")
                    log_details.append(f"quantity from {original_quantity} to {new_val}")
                    update_occurred = True
            except (ValueError, TypeError) as e: validation_errors["quantity"] = f"Invalid value: {e}"

        # Validate and update price (per unit for this purchase)
        if "price" in form_data:
            new_price_str = form_data.get("price")
            try:
                if new_price_str is None or new_price_str.strip() == '': raise ValueError("cannot be empty")
                new_val = float(new_price_str)
                if new_val < 0: raise ValueError("cannot be negative")
                if record.price is None or abs(record.price - new_val) > 1e-6:
                    record.price = new_val
                    price_updated = True
                    updated_fields.append("price")
                    log_details.append(f"price from {original_price:.2f} to {new_val:.2f}")
                    update_occurred = True
            except (ValueError, TypeError) as e: validation_errors["price"] = f"Invalid value: {e}"

        # Validate and update max_total_ml (size of package/bottle for this item)
        if "max_total_ml" in form_data:
            new_max_str = form_data.get("max_total_ml")
            try:
                new_val = 0.0 # Default if empty
                if new_max_str is not None and new_max_str.strip() != '':
                    new_val = float(new_max_str)
                    if new_val < 0: raise ValueError("cannot be negative")

                if record.max_total_ml is None or abs(record.max_total_ml - new_val) > 1e-6:
                    record.max_total_ml = new_val
                    updated_fields.append("max_total_ml")
                    log_details.append(f"max_total_ml from {original_max_ml:.1f} to {new_val:.1f}")
                    update_occurred = True
            except (ValueError, TypeError) as e: validation_errors["max_total_ml"] = f"Invalid value: {e}"

        if validation_errors:
             return jsonify(error={"message": "Validation failed", "errors": validation_errors}), 400

        # Recalculate total_price if quantity or price changed
        if quantity_updated or price_updated:
            if record.quantity is not None and record.price is not None:
                new_total_price = record.quantity * record.price
                if record.total_price is None or abs(record.total_price - new_total_price) > 1e-6:
                    record.total_price = new_total_price
                    log_details.append(f"total_price recalculated to {new_total_price:.2f}")
                    update_occurred = True # Mark as updated even if only total_price changed
            else:
                 current_app.logger.warning(f"Cannot recalculate total_price for inventory {inventory_id}.")

        if not update_occurred:
            return jsonify(message="No valid fields provided for update or no changes detected."), 200

        # Log Inventory Record Update
        log_description = f"Inventory item '{record.item_name}' (ID: {inventory_id}) PATCHed by user {updater_user.email}. Updated: {'; '.join(log_details)}."
        inventory_update_log = log_inventory_change(
            inventory_id=record.inventory_id,
            user_id=updater_user_id,
            change_type="update",
            description=log_description
        )
        if not inventory_update_log:
             db.session.rollback()
             current_app.logger.error(f"Failed to log inventory update (Inv ID {inventory_id}). Transaction rolled back.")
             return jsonify(error={"message": "Failed to create activity log. Update not saved."}), 500

        # Commit Transaction
        db.session.commit()
        current_app.logger.info(f"Inventory record {inventory_id} updated successfully via PATCH.")

        # Prepare and Return Response
        updated_record = db.session.get(Inventory, inventory_id) # Re-fetch
        response_data = {
            "inventory_id": updated_record.inventory_id,
            "inventory_container_id": updated_record.inventory_container_id,
            "greenhouse_id": updated_record.greenhouse_id,
            "item_name": updated_record.item_name,
            "user_name": updated_record.user_name,
            "type": updated_record.type,
            "quantity": int(updated_record.quantity) if updated_record.quantity is not None else 0,
            "total_price": float(updated_record.total_price) if updated_record.total_price is not None else 0.0,
            "max_total_ml": float(updated_record.max_total_ml) if updated_record.max_total_ml is not None else 0.0,
            "created_at": format_datetime(updated_record.created_at),
            "price": float(updated_record.price) if updated_record.price is not None else 0.0,
        }
        # Send Notification
        send_notification('inventory_updates', {"action": "update", "inventory": response_data})
        send_notification('inventory_logs_updates', {"action": "insert", "log_id": inventory_update_log.log_id, "inventory_id": inventory_id, "user_id": updater_user_id})


        return jsonify(message="Inventory record updated successfully", inventory=response_data), 200

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        current_app.logger.error(f"DB error patching inventory {inventory_id}: {e}", exc_info=True)
        orig_error = str(getattr(e, 'orig', e))
        status_code = 400
        msg = f"Database error: {orig_error}"
        if isinstance(e, IntegrityError): status_code = 409
        elif isinstance(e, DataError): msg = f"Invalid data format: {orig_error}"
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error patching inventory {inventory_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# --- DELETE Endpoint ---
@inventory_api.delete("/inventory/<int:inventory_id>")
def delete_inventory_record(inventory_id):
    """
    Deletes an inventory item record (e.g., correcting a mistaken entry).
    Requires email of deleter for logging.
    NOTE: This does NOT adjust InventoryContainer levels. It only removes the
          record of the purchase/addition. Use a 'usage' endpoint to decrease levels.
    """
    api_key_error = check_api_key(request)
    if api_key_error:
        return api_key_error

    try:
        # Require email for logging
        deleter_email = request.args.get("email") # Get from query param for DELETE
        if not deleter_email or not deleter_email.strip():
            return jsonify(error={"message": "Deleter email is required as a query parameter (?email=...) for logging."}), 400

        deleter_user = Users.query.filter(func.lower(Users.email) == func.lower(deleter_email)).first()
        if not deleter_user:
            return jsonify(error={"message": f"User with email '{deleter_email}' not found."}), 404
        deleter_user_id = deleter_user.user_id

        record = db.session.get(Inventory, inventory_id)
        if not record:
            return jsonify(error={"message": "Inventory record not found"}), 404

        deleted_item_name = record.item_name
        deleted_item_type = record.type
        deleted_greenhouse_id = record.greenhouse_id

        # Log Deletion of the Inventory Item
        log_description = f"Deleted inventory item '{deleted_item_name}' (ID: {inventory_id}, Type: {deleted_item_type}, GH: {deleted_greenhouse_id}) by user {deleter_user.email}."

        inventory_delete_log = log_inventory_change(
            inventory_id=inventory_id,
            user_id=deleter_user_id,
            change_type="delete",
            description=log_description
        )
        if not inventory_delete_log:
             db.session.rollback()
             current_app.logger.error(f"Failed to log inventory deletion (Inv ID {inventory_id}). Transaction rolled back.")
             return jsonify(error={"message": "Failed to create activity log. Deletion failed."}), 500

        # Delete the Inventory record
        # Note: Associated InventoryLogs might be deleted via cascade if set up in model,
        # otherwise they remain but point to a non-existent inventory_id (or FK constraint fails).
        # Ensure cascade is set on InventoryLog.inventory relationship if logs should be deleted.
        db.session.delete(record)

        # Commit
        db.session.commit()
        current_app.logger.info(f"Successfully deleted inventory record {inventory_id} ('{deleted_item_name}').")

        # Send Notifications
        send_notification('inventory_updates', {"action": "delete", "inventory_id": inventory_id, "greenhouse_id": deleted_greenhouse_id})
        send_notification('inventory_logs_updates', {"action": "insert", "log_id": inventory_delete_log.log_id, "inventory_id": inventory_id, "user_id": deleter_user_id})


        return jsonify(message=f"Inventory record '{deleted_item_name}' (ID: {inventory_id}) deleted successfully."), 200

    except IntegrityError as e:
         # This might happen if other tables (besides logs if cascade isn't set) reference this inventory item.
         db.session.rollback()
         current_app.logger.error(f"DB integrity error during inventory deletion for ID {inventory_id}: {e}", exc_info=True)
         orig_error = str(getattr(e, 'orig', e))
         msg = f"Cannot delete inventory item {inventory_id} due to existing database references: {orig_error}"
         return jsonify(error={"message": msg}), 409 # Conflict

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting inventory {inventory_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred during deletion."}), 500


# --- Inventory Container Routes ---

@inventory_api.get("/inventory/container")
def get_all_inventory_containers():
    """Retrieves all inventory container records, optionally filtered by greenhouse_id."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        greenhouse_id_filter = request.args.get('greenhouse_id', type=int)
        query = InventoryContainer.query.options(
            db.joinedload(InventoryContainer.greenhouses) # Eager load greenhouse info
        )
        if greenhouse_id_filter:
            query = query.filter(InventoryContainer.greenhouse_id == greenhouse_id_filter)

        containers = query.order_by(InventoryContainer.greenhouse_id).all()

        container_list = []
        for container in containers:
            container_list.append({
                "inventory_container_id": container.inventory_container_id,
                "greenhouse_id": container.greenhouse_id,
                "greenhouse_name": container.greenhouses.name if container.greenhouses else None,
                "ph_up": int(container.ph_up) if container.ph_up is not None else 0,
                "ph_down": int(container.ph_down) if container.ph_down is not None else 0,
                "solution_a": int(container.solution_a) if container.solution_a is not None else 0,
                "solution_b": int(container.solution_b) if container.solution_b is not None else 0,
                "critical_level": int(container.critical_level) if container.critical_level is not None else 0,
                # "inventory_id": container.inventory_id # Include if needed
            })

        count = len(container_list)
        message = f"Successfully retrieved {count} inventory container(s)."
        if count == 0:
             message = f"No inventory containers found for greenhouse {greenhouse_id_filter}." if greenhouse_id_filter else "No inventory containers found."

        return jsonify(message=message, count=count, inventory_containers=container_list), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching inventory containers: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred fetching containers."}), 500


@inventory_api.get("/inventory/container/<int:container_id>")
def get_inventory_container(container_id):
    """Gets a specific inventory container record by its ID."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        container = db.session.query(InventoryContainer).options(
             db.joinedload(InventoryContainer.greenhouses)
        ).get(container_id)

        if not container:
            return jsonify(error={"message": "Inventory container not found"}), 404

        container_data = {
            "inventory_container_id": container.inventory_container_id,
            "greenhouse_id": container.greenhouse_id,
            "greenhouse_name": container.greenhouses.name if container.greenhouses else None,
            "ph_up": int(container.ph_up) if container.ph_up is not None else 0,
            "ph_down": int(container.ph_down) if container.ph_down is not None else 0,
            "solution_a": int(container.solution_a) if container.solution_a is not None else 0,
            "solution_b": int(container.solution_b) if container.solution_b is not None else 0,
            "critical_level": int(container.critical_level) if container.critical_level is not None else 0,
            # "inventory_id": container.inventory_id
        }
        return jsonify(inventory_container=container_data), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching inventory container {container_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


@inventory_api.patch("/inventory/container/<int:container_id>")
def update_inventory_container(container_id):
    """
    Updates inventory container levels (ph_up, ph_down, solution_a, solution_b)
    and/or the critical_level.
    Requires 'email' of the updater for logging.
    Accepts fields like 'ph_up', 'ph_down', etc., in the form data.
    Logs changes made.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        updater_email = request.form.get("email")
        if not updater_email or not updater_email.strip():
             return jsonify(error={"message": "Updater email is required for logging."}), 400

        updater_user = Users.query.filter(func.lower(Users.email) == func.lower(updater_email)).first()
        if not updater_user:
            return jsonify(error={"message": f"User with email '{updater_email}' not found."}), 404
        updater_user_id = updater_user.user_id

        container = db.session.get(InventoryContainer, container_id)
        if not container:
            return jsonify(error={"message": "Inventory container not found"}), 404

        form_data = request.form
        updated_fields = []
        log_entries = [] # Store log objects to commit together
        validation_errors = {}
        update_occurred = False

        # Fields allowed for update via PATCH
        updatable_fields = ["ph_up", "ph_down", "solution_a", "solution_b", "critical_level"]

        for field in updatable_fields:
            if field in form_data:
                new_value_str = form_data.get(field)
                try:
                    if new_value_str is None or new_value_str.strip() == '':
                         raise ValueError("cannot be empty if provided")
                    new_value = int(new_value_str) # All container fields are integers
                    if new_value < 0: raise ValueError("cannot be negative")

                    old_value = getattr(container, field, 0)
                    if old_value != new_value:
                        setattr(container, field, new_value)
                        updated_fields.append(field)
                        update_occurred = True

                        # Prepare log entry for this field change
                        log_desc = f"Container {container_id} field '{field}' changed from {old_value} to {new_value} by user {updater_user.email}."
                        field_log = log_container_change(
                            container_id=container_id,
                            user_id=updater_user_id,
                            item=field,
                            old_quantity=old_value,
                            new_quantity=new_value,
                            description=log_desc,
                            change_type="manual_update" # Indicate manual adjustment
                        )
                        if field_log:
                            log_entries.append(field_log)
                        else:
                            # If logging fails for one field, stop and rollback
                            db.session.rollback()
                            current_app.logger.error(f"Failed to log container update for field '{field}' (Container ID {container_id}). Transaction rolled back.")
                            return jsonify(error={"message": f"Failed to create activity log for field '{field}'. Update failed."}), 500

                except (ValueError, TypeError) as e:
                    validation_errors[field] = f"Invalid value: {e}"
                except Exception as e: # Catch unexpected errors during logging prep
                     db.session.rollback()
                     current_app.logger.error(f"Unexpected error preparing log for container update field '{field}': {e}", exc_info=True)
                     return jsonify(error={"message": f"Internal error preparing log for field '{field}'."}), 500


        if validation_errors:
             return jsonify(error={"message": "Validation failed", "errors": validation_errors}), 400

        if not update_occurred:
            return jsonify(message="No valid fields provided for update or no changes detected."), 200

        # Commit container changes and all prepared log entries
        db.session.commit()
        current_app.logger.info(f"Inventory container {container_id} updated successfully by {updater_user.email}. Fields: {', '.join(updated_fields)}")

        # Prepare response data
        updated_container = db.session.get(InventoryContainer, container_id) # Re-fetch
        response_data = {
            "inventory_container_id": updated_container.inventory_container_id,
            "greenhouse_id": updated_container.greenhouse_id,
            "ph_up": int(updated_container.ph_up) if updated_container.ph_up is not None else 0,
            "ph_down": int(updated_container.ph_down) if updated_container.ph_down is not None else 0,
            "solution_a": int(updated_container.solution_a) if updated_container.solution_a is not None else 0,
            "solution_b": int(updated_container.solution_b) if updated_container.solution_b is not None else 0,
            "critical_level": int(updated_container.critical_level) if updated_container.critical_level is not None else 0,
        }

        # Send Notifications
        send_notification('inventory_container_updates', {"action": "update", "container": response_data})
        for log_entry in log_entries: # Send notification for each log created
             send_notification('inventory_container_logs_updates', {"action": "insert", "log_id": log_entry.log_id, "container_id": container_id, "user_id": updater_user_id})


        return jsonify(message="Inventory container updated successfully", inventory_container=response_data), 200

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        current_app.logger.error(f"DB error patching container {container_id}: {e}", exc_info=True)
        orig_error = str(getattr(e, 'orig', e))
        status_code = 400
        msg = f"Database error: {orig_error}"
        if isinstance(e, IntegrityError): status_code = 409
        elif isinstance(e, DataError): msg = f"Invalid data format: {orig_error}"
        return jsonify(error={"message": msg}), status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error patching container {container_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# --- Endpoint for Recording Usage (Example) ---
@inventory_api.post("/inventory/container/use")
def record_container_usage():
    """
    Records usage of a container item (ph_up, ph_down, solution_a, solution_b).
    Decreases the level in the corresponding InventoryContainer field.
    Requires: greenhouse_id, item_type (e.g., "ph_up"), quantity_used, email (of user).
    Logs the usage event.
    """
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        # --- Get Data ---
        form_data = request.form
        greenhouse_id = form_data.get("greenhouse_id", type=int)
        item_type = form_data.get("item_type") # e.g., "ph_up"
        quantity_used_str = form_data.get("quantity_used")
        user_email = form_data.get("email")

        # --- Validation ---
        errors = {}
        quantity_used = None

        if not greenhouse_id: errors["greenhouse_id"] = "Required."
        if not item_type or item_type.lower() not in CONTAINER_ITEM_TYPES:
             errors["item_type"] = f"Required and must be one of: {', '.join(CONTAINER_ITEM_TYPES)}."
        if not user_email: errors["email"] = "Required."

        try:
            if quantity_used_str is None: errors["quantity_used"] = "Required."
            else:
                quantity_used = int(quantity_used_str)
                if quantity_used <= 0: errors["quantity_used"] = "Must be positive."
        except (ValueError, TypeError): errors["quantity_used"] = "Must be a valid integer."

        if errors: return jsonify(error={"message": "Validation failed", "errors": errors}), 400

        # --- Find User ---
        user = Users.query.filter(func.lower(Users.email) == func.lower(user_email)).first()
        if not user: return jsonify(error={"message": f"User '{user_email}' not found."}), 404
        user_id = user.user_id

        # --- Find Container and Update Level ---
        container_field = item_type.lower()
        container = InventoryContainer.query.filter_by(
            greenhouse_id=greenhouse_id
        ).with_for_update().first() # Lock row

        if not container:
            return jsonify(error={"message": f"Inventory container for greenhouse {greenhouse_id} not found."}), 404

        old_level = getattr(container, container_field, 0)
        if old_level < quantity_used:
            return jsonify(error={"message": f"Insufficient quantity for '{container_field}'. Available: {old_level}, Used: {quantity_used}"}), 400 # Bad request - insufficient stock

        new_level = old_level - quantity_used
        setattr(container, container_field, new_level)
        db.session.add(container)

        # --- Log Usage ---
        log_desc = f"Recorded usage of {quantity_used} units of '{container_field}' by user {user.email}. Level changed from {old_level} to {new_level}."
        usage_log = log_container_change(
            container_id=container.inventory_container_id,
            user_id=user_id,
            item=container_field,
            old_quantity=old_level,
            new_quantity=new_level,
            description=log_desc,
            change_type="usage" # Specific type for usage
        )
        if not usage_log:
             db.session.rollback()
             current_app.logger.error(f"Failed to log container usage (Container ID {container.inventory_container_id}). Transaction rolled back.")
             return jsonify(error={"message": "Failed to create activity log. Usage not recorded."}), 500

        # --- Commit and Notify ---
        db.session.commit()
        current_app.logger.info(f"Recorded usage for container {container.inventory_container_id}, item '{container_field}', quantity {quantity_used} by user {user.email}.")

        # Prepare response data
        response_data = {
            "inventory_container_id": container.inventory_container_id,
            "greenhouse_id": container.greenhouse_id,
            "item_type": container_field,
            "quantity_used": quantity_used,
            "new_level": new_level,
            "user_email": user.email
        }

        # Send Notifications
        send_notification('inventory_container_updates', {"action": "usage", "usage_details": response_data})
        send_notification('inventory_container_logs_updates', {"action": "insert", "log_id": usage_log.log_id, "container_id": container.inventory_container_id, "user_id": user_id})


        return jsonify(message="Inventory usage recorded successfully", usage_record=response_data), 200

    except (IntegrityError, DataError) as e:
        db.session.rollback()
        current_app.logger.error(f"DB error recording inventory usage: {e}", exc_info=True)
        orig_error = str(getattr(e, 'orig', e))
        return jsonify(error={"message": f"Database error: {orig_error}"}), 400 # Or 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error recording inventory usage: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500

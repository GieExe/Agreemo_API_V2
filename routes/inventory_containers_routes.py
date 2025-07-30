# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\inventory_containers_routes.py
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
import os
import traceback # Keep traceback import for detailed error response

# Assuming 'db' is your SQLAlchemy instance initialized elsewhere
from db import db
# Import your database models
from models.inventory_model import InventoryContainer
from models.activity_logs.inventory_container_activity_logs import InventoryContainerLog
from models.users_model import Users
from models.greenhouses_model import Greenhouse

inventory_container_api = Blueprint("inventory_container_api", __name__)

# Consistent API Key loading and Timezone
API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace")
PH_TZ = pytz.timezone('Asia/Manila')

# --- Helper Functions (check_api_key, format_datetime, log_container_action) ---
# Keep these helpers as defined in the previous corrected version

def check_api_key(request):
    # ... (implementation) ...
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        current_app.logger.warning(f"Failed API key attempt. Provided key starts with: '{str(api_key_header)[:4]}...'")
        return jsonify(error={"Not Authorised": "Incorrect or missing api_key."}), 403
    return None

def format_datetime(dt):
    # ... (implementation) ...
    if not dt or not isinstance(dt, datetime):
        current_app.logger.debug(f"format_datetime received invalid input: {type(dt)}")
        return None
    try:
        dt_aware = None
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            dt_aware = PH_TZ.localize(dt)
        else:
            dt_aware = dt.astimezone(PH_TZ)
        return dt_aware.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        current_app.logger.error(f"Could not format datetime {dt} to PH time format: {e}. Falling back to ISO format.", exc_info=True)
        try:
            return dt.isoformat()
        except Exception as fallback_e:
             current_app.logger.error(f"Could not format datetime {dt} to ISO format: {fallback_e}. Falling back to string.", exc_info=True)
             return str(dt)

def log_container_action(container_id, user_id, change_type, description, item=None, old_value=None, new_value=None, user_email_for_desc="N/A"):
    # ... (implementation - ensures int quantities) ...
    try:
        old_qty_log = int(old_value) if old_value is not None else None
        new_qty_log = int(new_value) if new_value is not None else None
        log_entry = InventoryContainerLog(
            inventory_container_id=container_id, user_id=user_id,
            change_type=str(change_type).lower(),
            item=str(item) if item is not None else None,
            old_quantity=old_qty_log, new_quantity=new_qty_log,
            description=f"{description} | Triggered by User Email: {user_email_for_desc}",
        )
        db.session.add(log_entry)
        current_app.logger.info(f"Prepared InventoryContainerLog for container {container_id}, user_id {user_id}, change_type {change_type}")
    except Exception as e:
        current_app.logger.error(f"Failed to prepare InventoryContainerLog entry for container {container_id} (user_id {user_id}): {e}", exc_info=True)
        raise

# --- Routes ---

@inventory_container_api.post("/inventory_container")
def create_inventory_container():
    """Creates a new inventory container. 'inventory_id' from form is ignored for container creation."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    form_data = request.form
    # Although inventory_id is required in the form, it's NOT used for InventoryContainer itself
    required_fields = ["greenhouse_id", "inventory_id", "email"]
    missing_fields = [field for field in required_fields if field not in form_data or not form_data.get(field)]
    if missing_fields:
        return jsonify(error={"message": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    creator_email = form_data.get("email")
    greenhouse_id_str = form_data.get("greenhouse_id")
    # inventory_id_str is read from form but NOT used for InventoryContainer directly
    inventory_id_str = form_data.get("inventory_id")

    try:
        # --- Validate User ---
        user = Users.query.filter(Users.email.ilike(creator_email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{creator_email}' not found."}), 404

        # --- Validate Greenhouse ID ---
        try:
            greenhouse_id = int(greenhouse_id_str)
            greenhouse = db.session.get(Greenhouse, greenhouse_id)
            if not greenhouse:
                return jsonify(error={"message": f"Greenhouse with ID {greenhouse_id} not found."}), 404
        except (ValueError, TypeError):
            return jsonify(error={"message": "Invalid 'greenhouse_id' format. Must be an integer."}), 400

        # --- Validate format of inventory_id (but don't use it for container) ---
        try:
            _ = int(inventory_id_str) # Check if it's an int, but discard the value
        except (ValueError, TypeError):
             return jsonify(error={"message": "Invalid 'inventory_id' format. Must be an integer."}), 400

        # --- Check for Existing Container ---
        existing_container = InventoryContainer.query.filter_by(greenhouse_id=greenhouse_id).first()
        if existing_container:
            return jsonify(error={"message": f"An inventory container already exists for Greenhouse ID {greenhouse_id}."}), 409

        # --- Validate Optional Numeric Fields as INTEGERS ---
        # Initialize container_args WITHOUT inventory_id
        container_args = {
            "greenhouse_id": greenhouse_id,
        }
        allowed_numeric_fields = ["ph_up", "ph_down", "solution_a", "solution_b", "critical_level"]
        validation_errors = {}

        # (Validation loop remains the same, adding valid ints to container_args)
        for field in allowed_numeric_fields:
            if field in form_data:
                value_str = form_data.get(field)
                if value_str is None or value_str.strip() == '':
                    validation_errors[field] = f"Value for '{field}' cannot be empty (must be a non-negative integer)."
                else:
                    try:
                        value_int = int(value_str)
                        if value_int < 0:
                             raise ValueError(f"Value for '{field}' cannot be negative.")
                        container_args[field] = value_int
                    except (ValueError, TypeError) as e:
                        validation_errors[field] = f"Invalid integer value ('{value_str}') for '{field}': {str(e)}"

        if validation_errors:
            return jsonify(error={"message": "Validation failed", "errors": validation_errors}), 400

        # --- Create New Container Instance (inventory_id is NOT passed) ---
        new_container = InventoryContainer(**container_args)

        # --- Add, Flush, Log, Commit ---
        db.session.add(new_container)
        db.session.flush()
        current_app.logger.info(f"Flushed session, assigned ID {new_container.inventory_container_id} to new container for GH {greenhouse_id}.")

        # Log description updated - no inventory_id
        log_description = f"Inventory Container created for GH: {greenhouse_id}."
        log_container_action(
            container_id=new_container.inventory_container_id,
            user_id=user.user_id, change_type="create", description=log_description,
            user_email_for_desc=user.email
        )

        db.session.commit()
        current_app.logger.info(f"Successfully committed Inventory Container ID {new_container.inventory_container_id} (user {user.email}).")

        # --- Prepare Response Data (NO inventory_id) ---
        response_data = {
            "inventory_container_id": new_container.inventory_container_id,
            "greenhouse_id": new_container.greenhouse_id,
            # "inventory_id": new_container.inventory_id, # REMOVED
            "ph_up": int(new_container.ph_up),
            "ph_down": int(new_container.ph_down),
            "solution_a": int(new_container.solution_a),
            "solution_b": int(new_container.solution_b),
            "critical_level": int(new_container.critical_level),
        }

        return jsonify(
            message="Inventory container created successfully",
            inventory_container=response_data
        ), 201

    # --- Keep the DETAILED error response for debugging (use with caution) ---
    except Exception as e:
        db.session.rollback()
        error_traceback = traceback.format_exc()
        current_app.logger.error(
            f"Error creating inventory container for GH {greenhouse_id_str} (user {creator_email}): {e}\nTRACEBACK:\n{error_traceback}")
        error_payload = {
            "message": "An internal server error occurred.",
            "error_type": type(e).__name__,
            "error_details": str(e),
        }
        current_app.logger.warning(
            "Returning detailed error information in API response during debugging. Ensure this is disabled in production.")
        return jsonify(error=error_payload), 500


@inventory_container_api.get("/inventory_container/greenhouse/<int:greenhouse_id>")
def get_inventory_container_for_greenhouse(greenhouse_id):
    """Gets the inventory container associated with a specific greenhouse ID."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        container = InventoryContainer.query.filter_by(greenhouse_id=greenhouse_id).first()
        if container:
            container_data = {
                "inventory_container_id": container.inventory_container_id,
                "greenhouse_id": container.greenhouse_id,
                # "inventory_id": container.inventory_id, # REMOVED
                "ph_up": int(container.ph_up),
                "ph_down": int(container.ph_down),
                "solution_a": int(container.solution_a),
                "solution_b": int(container.solution_b),
                "critical_level": int(container.critical_level),
            }
            return jsonify(inventory_container=container_data), 200
        else:
            return jsonify(message="Inventory container not found for this greenhouse"), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching container for greenhouse {greenhouse_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500

@inventory_container_api.get("/inventory_container/<int:container_id>")
def get_inventory_container_by_id(container_id):
    """Gets a specific inventory container by its ID."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        container = db.session.get(InventoryContainer, container_id)
        if container:
            container_data = {
                "inventory_container_id": container.inventory_container_id,
                "greenhouse_id": container.greenhouse_id,
                # "inventory_id": container.inventory_id, # REMOVED
                "ph_up": int(container.ph_up),
                "ph_down": int(container.ph_down),
                "solution_a": int(container.solution_a),
                "solution_b": int(container.solution_b),
                "critical_level": int(container.critical_level),
            }
            return jsonify(inventory_container=container_data), 200
        else:
            return jsonify(message=f"Inventory container with ID {container_id} not found"), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching container ID {container_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500

@inventory_container_api.get("/inventory_container")
def get_all_inventory_containers():
    """Gets all inventory containers, ordered by greenhouse ID."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    try:
        containers = InventoryContainer.query.order_by(InventoryContainer.greenhouse_id).all()
        container_list = [{
            "inventory_container_id": c.inventory_container_id,
            "greenhouse_id": c.greenhouse_id,
            # "inventory_id": c.inventory_id, # REMOVED
            "ph_up": int(c.ph_up),
            "ph_down": int(c.ph_down),
            "solution_a": int(c.solution_a),
            "solution_b": int(c.solution_b),
            "critical_level": int(c.critical_level),
        } for c in containers]
        return jsonify(inventory_containers=container_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all inventory containers: {e}", exc_info=True)
        return jsonify(error={"message": "An Rnder server error occurred."}), 500


@inventory_container_api.delete("/inventory_container/<int:container_id>")
def delete_inventory_container(container_id):
    """Deletes an inventory container by its ID. Requires user email in form data."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    deleter_email = request.form.get("email")
    if not deleter_email:
        return jsonify(error={"message": "User email is required in form data for logging."}), 400
    try:
        user = Users.query.filter(Users.email.ilike(deleter_email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{deleter_email}' not found."}), 404
        container = db.session.get(InventoryContainer, container_id)
        if not container:
            return jsonify(message=f"Inventory container with ID {container_id} not found"), 404

        gh_id = container.greenhouse_id
        # inv_id = container.inventory_id # REMOVED - doesn't exist on container
        # Log description updated - no inventory_id
        log_description = f"Inventory Container (ID: {container_id}, linked to GH: {gh_id}) deleted"
        log_container_action(
             container_id=container_id, user_id=user.user_id, change_type="delete",
             description=log_description, user_email_for_desc=user.email
         )
        db.session.delete(container)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted inventory container {container_id} (user {user.email}).")
        return jsonify(message="Inventory container deleted successfully"), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting container {container_id} by user {deleter_email}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred during deletion."}), 500


@inventory_container_api.patch("/inventory_container/<int:container_id>")
def patch_inventory_container(container_id):
    """Partially updates inventory container values (Integers) using form data."""
    # (PATCH route remains the same as the last correct version - it doesn't reference inventory_id)
    # ... (ensure PATCH code is the version handling Integers correctly) ...
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error
    updater_email = request.form.get("email")
    if not updater_email:
        return jsonify(error={"message": "User email is required in form data for logging."}), 400
    try:
        user = Users.query.filter(Users.email.ilike(updater_email)).first()
        if not user:
             return jsonify(error={"message": f"User with email '{updater_email}' not found."}), 404
        container = db.session.get(InventoryContainer, container_id)
        if not container:
             return jsonify(message=f"Inventory container with ID {container_id} not found"), 404

        updated_fields = []
        fields_to_log = []
        allowed_fields_types = {
             "ph_up": int, "ph_down": int, "solution_a": int,
             "solution_b": int, "critical_level": int
        }
        validation_errors = {}
        form_data = request.form

        for field, expected_type in allowed_fields_types.items():
            if field in form_data:
                value_str = form_data.get(field)
                if value_str is None or value_str.strip() == '':
                    validation_errors[field] = f"Value for non-nullable field '{field}' cannot be empty."
                    continue
                try:
                    new_value = expected_type(value_str)
                    if new_value < 0:
                         raise ValueError(f"Value for '{field}' cannot be negative.")
                    old_value = getattr(container, field)
                    if old_value != new_value:
                         setattr(container, field, new_value)
                         updated_fields.append(field)
                         fields_to_log.append((field, old_value, new_value))
                except (ValueError, TypeError) as e:
                    validation_errors[field] = f"Invalid integer value ('{value_str}') for '{field}': {str(e)}"
                except Exception as e:
                     current_app.logger.error(f"Unexpected error processing field {field} for container {container_id}: {e}", exc_info=True)
                     validation_errors[field] = f"Processing error for '{field}'"

        if validation_errors:
            return jsonify(error={"message": "Validation failed", "errors": validation_errors}), 400
        if not updated_fields:
            return jsonify(message="No changes detected or no valid fields provided for update."), 200

        base_log_desc = f"PATCH update on container {container_id}."
        for item, old_val, new_val in fields_to_log:
            old_val_str = str(old_val)
            new_val_str = str(new_val)
            item_log_desc = f"{base_log_desc} Changed '{item}' from {old_val_str} to {new_val_str}."
            log_container_action(
                container_id=container_id, user_id=user.user_id, change_type="update",
                item=item, old_value=old_val, new_value=new_val,
                description=item_log_desc, user_email_for_desc=user.email
            )

        db.session.commit()
        current_app.logger.info(f"Inventory container {container_id} updated successfully (user {user.email}). Fields: {', '.join(updated_fields)}")

        updated_container = db.session.get(InventoryContainer, container_id)
        response_data = {
            "inventory_container_id": updated_container.inventory_container_id,
            "greenhouse_id": updated_container.greenhouse_id,
            # "inventory_id": updated_container.inventory_id, # REMOVED
            "ph_up": int(updated_container.ph_up),
            "ph_down": int(updated_container.ph_down),
            "solution_a": int(updated_container.solution_a),
            "solution_b": int(updated_container.solution_b),
            "critical_level": int(updated_container.critical_level),
        }
        return jsonify(
            message="Inventory container updated successfully",
            inventory_container=response_data
         ), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error patching container {container_id} (user {updater_email}): {e}", exc_info=True)
        # Using the detailed error response block for debugging PATCH as well
        error_traceback = traceback.format_exc()
        current_app.logger.error(
            f"Error patching container {container_id} (user {updater_email}): {e}\nTRACEBACK:\n{error_traceback}")
        error_payload = {
            "message": "An internal server error occurred during update.",
            "error_type": type(e).__name__,
            "error_details": str(e),
        }
        current_app.logger.warning(
            "Returning detailed error information in API response during debugging. Ensure this is disabled in production.")
        return jsonify(error=error_payload), 500
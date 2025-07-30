# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\nutrient_controllers_routes.py
import pytz
from datetime import datetime
import os
from flask import Blueprint, request, jsonify, current_app

from db import db
# Ensure correct model imports from your project structure
from models.greenhouses_model import Greenhouse
from models.users_model import Users
from models.planted_crops_model import PlantedCrops
from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs
from models.nutrient_controllers_model import NutrientController
from models.inventory_model import InventoryContainer
from models.activity_logs.inventory_container_activity_logs import InventoryContainerLog


nutrient_controllers_api = Blueprint("nutrient_controllers_api", __name__)

API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace") # Use default
PH_TZ = pytz.timezone('Asia/Manila')


# --- Helper Functions ---
def check_api_key(request):
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403
    return None

def format_datetime(dt):
    if not dt: return None
    # Use consistent formatting, handling potential timezone from DB if needed
    return dt.strftime("%Y-%m-%d %H:%M:%S") if isinstance(dt, datetime) else None

# Reuse container log helper, passing user email for description
# Assumes Inventory Container Log table has NOT been changed
def log_container_change(container_id, user_email, change_type, item, old_value, new_value, base_description):
    """Helper to log container changes, adding user email to description."""
    try:
        # Example: Append user email for tracking
        full_description = f"{base_description} | User: {user_email}"

        log_entry = InventoryContainerLog(
            inventory_container_id=container_id,
            # user_id = ? # Cannot set if model not changed
            change_type=change_type,
            item=item,
            old_quantity=old_value,
            new_quantity=new_value,
            description=full_description, # Include user info here
            timestamp=datetime.now(pytz.utc) # Set timestamp explicitly
        )
        db.session.add(log_entry)
        current_app.logger.info(f"Prepared InventoryContainerLog: {full_description}")
        # DO NOT COMMIT HERE - handled by calling route
    except Exception as e:
        current_app.logger.error(f"Failed to prepare container log (user {user_email}): {e}", exc_info=True)
        raise

def log_nutrient_controller_activity(controller_id, greenhouse_id, activated_by_str, description):
    """Creates and adds nutrient controller activity log."""
    try:
        log_time_naive = datetime.now(PH_TZ).replace(tzinfo=None) # Use naive time
        new_nc_log = NutrientControllerActivityLogs(
            controller_id=controller_id,
            greenhouse_id=greenhouse_id,
            activated_by=activated_by_str, # Store the string (e.g., user name, "Auto")
            logs_description=description,
            logs_date=log_time_naive
        )
        db.session.add(new_nc_log)
        db.session.flush() # Assigns log_id
        current_app.logger.info(f"Prepared NutrientControllerActivityLog for controller {controller_id} activated by '{activated_by_str}'.")
        return new_nc_log
        # DO NOT COMMIT HERE
    except Exception as e:
         current_app.logger.error(f"Failed to prepare nutrient controller log (activated by {activated_by_str}): {e}", exc_info=True)
         raise

# --- Routes ---

@nutrient_controllers_api.get("/nutrient_controllers")
def get_all_nutrient_controllers():
    """Gets all nutrient controller records."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        # Add optional filters
        greenhouse_id_filter = request.args.get('greenhouse_id', type=int)
        plant_id_filter = request.args.get('plant_id', type=int)

        query = NutrientController.query
        if greenhouse_id_filter:
            query = query.filter(NutrientController.greenhouse_id == greenhouse_id_filter)
        if plant_id_filter:
            query = query.filter(NutrientController.plant_id == plant_id_filter)

        query_data = query.order_by(NutrientController.dispensed_time.desc()).all()

        # Return 200 empty list if filter applied, 404 only if truly nothing exists
        if not query_data and not (greenhouse_id_filter or plant_id_filter):
             return jsonify(message="No nutrient controller records found.", nutrient_controllers=[]), 404
        elif not query_data:
             return jsonify(message="No nutrient controller records found matching criteria.", nutrient_controllers=[]), 200

        nutrient_controllers_list = [{
            "controller_id": data.controller_id,
            "greenhouse_id": data.greenhouse_id,
            "plant_id": data.plant_id,
            "plant_name": data.plant_name,     # Included from model
            "solution_type": data.solution_type,
            "dispensed_amount": float(data.dispensed_amount) if data.dispensed_amount is not None else None,
            "activated_by": data.activated_by, # String field from model
            "dispensed_time": format_datetime(data.dispensed_time)
        } for data in query_data]

        current_app.logger.info(f"Fetched {len(nutrient_controllers_list)} nutrient controller records.")
        return jsonify(nutrient_controllers=nutrient_controllers_list), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching nutrient controller records: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


@nutrient_controllers_api.get("/nutrient_controllers/<int:controller_id>")
def get_nutrient_controller_by_id(controller_id):
    """Gets a specific nutrient controller record by its ID."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    try:
        controller = db.session.get(NutrientController, controller_id)
        if not controller:
            current_app.logger.warning(f"NutrientController ID {controller_id} not found.")
            return jsonify(message=f"Nutrient controller with ID {controller_id} not found"), 404

        controller_data = {
            "controller_id": controller.controller_id,
            "greenhouse_id": controller.greenhouse_id,
            "plant_id": controller.plant_id,
            "plant_name": controller.plant_name,     # Included from model
            "solution_type": controller.solution_type,
            "dispensed_amount": float(controller.dispensed_amount) if controller.dispensed_amount is not None else None,
            "activated_by": controller.activated_by, # String field from model
            "dispensed_time": format_datetime(controller.dispensed_time)
        }

        current_app.logger.info(f"Fetched NutrientController ID {controller_id}")
        return jsonify(nutrient_controller=controller_data), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching nutrient controller {controller_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


@nutrient_controllers_api.post("/nutrient_controllers")
def add_nutrient_controller():
    """Adds a nutrient controller event, updates inventory, and logs activity."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # --- Extract Data ---
    greenhouse_id_str = request.form.get("greenhouse_id")
    plant_id_str = request.form.get("plant_id")
    solution_type = request.form.get("solution_type")
    dispensed_amount_str = request.form.get("dispensed_amount")
    # Get 'email' to determine 'activated_by'. Allow special value like "Auto"
    trigger_email = request.form.get("email") # Changed name for clarity

    # --- Basic Validation ---
    errors = {}
    if not greenhouse_id_str: errors['greenhouse_id'] = "Required."
    if not plant_id_str: errors['plant_id'] = "Required."
    if not solution_type: errors['solution_type'] = "Required."
    if not dispensed_amount_str: errors['dispensed_amount'] = "Required."
    if not trigger_email: errors['email'] = "Required (email or 'Auto')."

    if errors:
        return jsonify(error={"message": "Missing required fields.", "details": errors}), 400

    # --- More Detailed Validation & Conversions ---
    user = None
    plant = None
    activated_by_str = "Unknown" # Default if lookup fails but proceeds
    greenhouse_id = None
    plant_id = None
    dispensed_amount = None

    try:
        greenhouse_id = int(greenhouse_id_str)
        plant_id = int(plant_id_str)
        dispensed_amount = float(dispensed_amount_str)

        if dispensed_amount <= 0:
            errors['dispensed_amount'] = "Must be a positive number."

        # Validate solution type from constraint list
        allowed_solutions = ['pH Up', 'pH Down', 'Nutrient A', 'Nutrient B']
        if solution_type not in allowed_solutions:
             errors['solution_type'] = f"Invalid solution_type. Must be one of: {', '.join(allowed_solutions)}"

        # Find Greenhouse
        greenhouse = db.session.get(Greenhouse, greenhouse_id)
        if not greenhouse:
            errors['greenhouse_id'] = f"Greenhouse with ID {greenhouse_id} not found."

        # Find Plant and get its name
        plant = db.session.get(PlantedCrops, plant_id)
        if not plant:
            errors['plant_id'] = f"Planted crop with ID {plant_id} not found."
        elif greenhouse and plant and plant.greenhouse_id != greenhouse_id:
             # Optional check if plant belongs to the correct greenhouse
             errors['plant_id'] = f"Plant {plant_id} does not belong to greenhouse {greenhouse_id}."

        # Determine 'activated_by' string based on email/trigger
        if trigger_email.lower() == "auto":
            activated_by_str = "Auto"
        else:
            user = Users.query.filter_by(email=trigger_email).first()
            if user:
                activated_by_str = f"{user.first_name} {user.last_name}" # Use user's full name
            else:
                # If email provided but user not found
                errors['email'] = f"User with email '{trigger_email}' not found."
                activated_by_str = f"user_not_found ({trigger_email})" # Log attempt

        # Check validation results before proceeding
        if errors:
            current_app.logger.warning(f"Validation errors adding nutrient controller event: {errors}")
            return jsonify(error={"message": "Validation failed.", "details": errors}), 400

        # --- Inventory Update ---
        inventory_container = InventoryContainer.query.filter_by(greenhouse_id=greenhouse_id).first()
        if not inventory_container:
             # No rollback needed yet as no changes made
            return jsonify(error={"message": f"Inventory container not found for greenhouse {greenhouse_id}."}), 404

        # Map solution type to container field name
        item_map = {
            'pH Up': ('ph_up', inventory_container.ph_up),
            'pH Down': ('ph_down', inventory_container.ph_down),
            'Nutrient A': ('solution_a', inventory_container.solution_a),
            'Nutrient B': ('solution_b', inventory_container.solution_b),
        }
        item_field, current_inventory = item_map.get(solution_type, (None, None))

        if not item_field:
            # Should not happen if solution_type validation passed, but safety check
            return jsonify(error={"message": "Internal mapping error for solution type."}), 500

        if current_inventory is None or current_inventory < dispensed_amount:
            # Check if None is possible or only insufficient amount
            return jsonify(error={"message": f"Not enough {solution_type} ({current_inventory} ml) in inventory container for greenhouse {greenhouse_id} to dispense {dispensed_amount} ml."}), 400

        # Store old value before decrementing
        old_inventory_value = current_inventory
        new_inventory_value = old_inventory_value - dispensed_amount
        setattr(inventory_container, item_field, new_inventory_value) # Decrement inventory

        # --- Prepare DB Objects (Add all before commit) ---
        log_time_naive = datetime.now(PH_TZ).replace(tzinfo=None)

        # 1. Create NutrientController Record
        new_controller = NutrientController(
            greenhouse_id=greenhouse_id,
            plant_id=plant_id,
            plant_name=plant.plant_name, # Use the actual plant name
            solution_type=solution_type,
            dispensed_amount=dispensed_amount,
            activated_by=activated_by_str, # Use the determined string
            dispensed_time=log_time_naive
        )
        db.session.add(new_controller)
        db.session.flush() # Get controller_id

        # 2. Prepare InventoryContainerLog (Uses log_container_change helper)
        inventory_log_desc = f"Dispensed {dispensed_amount} ml of {solution_type} for plant '{plant.plant_name}' (ID: {plant.id})."
        log_container_change(
             inventory_container.inventory_container_id,
             trigger_email, # Log who triggered it (even if just email)
             "remove", # Change type for dispensing
             item_field, # e.g., 'ph_up'
             old_inventory_value,
             new_inventory_value,
             inventory_log_desc
        ) # Will add log to session

        # 3. Prepare NutrientControllerActivityLog (Uses log_nutrient_controller_activity helper)
        nc_log_description = f"Nutrient dose of {dispensed_amount}ml {solution_type} applied to plant '{plant.plant_name}' (ID: {plant_id})."
        new_nc_log = log_nutrient_controller_activity(
            controller_id=new_controller.controller_id,
            greenhouse_id=greenhouse_id,
            activated_by_str=activated_by_str,
            description=nc_log_description
        ) # Will add log to session

        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(f"Nutrient controller event {new_controller.controller_id} added and inventory updated for GID:{greenhouse_id}, activated by '{activated_by_str}'.")

        # --- Send Notifications (if needed) ---
        # send_notification('nutrient_controller_updates', {"action": "insert", "controller_id": new_controller.controller_id})
        # send_notification('nutrient_controller_logs_updates', {"action": "insert", "log_id": new_nc_log.log_id})
        # send_notification('inventory_container_logs_updates', {"action": "insert", ...}) # If you track inv container logs

        return jsonify(
            message="Nutrient controller event recorded and inventory updated successfully.",
            controller_id=new_controller.controller_id
        ), 201

    except Exception as e:
        db.session.rollback() # Rollback any partial changes
        current_app.logger.error(f"Error adding nutrient controller event: {e}", exc_info=True)
        # Consider checking specific error types (IntegrityError, etc.) for more specific messages
        return jsonify(error={"message": "An internal server error occurred."}), 500


@nutrient_controllers_api.delete("/nutrient_controllers")
def delete_all_nutrient_controllers():
    """Deletes ALL nutrient controller records. Highly destructive. Requires email and confirmation."""
    api_key_error = check_api_key(request)
    if api_key_error: return api_key_error

    # Add safeguards for such a destructive action
    deleter_email = request.form.get("email")
    confirmation = request.form.get("confirmation")

    if not deleter_email:
         return jsonify(error={"message": "User email is required in form data for logging."}), 400
    if confirmation != "DELETE ALL NUTRIENT CONTROLLER DATA":
         return jsonify(error={"message": "Missing or incorrect confirmation phrase."}), 400

    try:
        # --- Validate User ---
        user = Users.query.filter_by(email=deleter_email).first()
        if not user:
            # Allow deletion even if user not found, but log the attempt? Or deny? Denying is safer.
            current_app.logger.warning(f"Attempt to delete ALL nutrient controllers by non-existent user '{deleter_email}' denied.")
            return jsonify(error={"message": f"User with email '{deleter_email}' not found."}), 404
        deleter_id = user.user_id # Needed if you add user_id to logs

        # --- Log the Intent (before deleting) ---
        # It's hard to log details per record when deleting all. Log the bulk action.
        log_description = f"Attempting to delete ALL NutrientController records. Action initiated by user {user.email} (ID: {user.user_id})."
        # Note: Can't use the helper directly as we don't have a single controller_id yet
        # Consider adding a system-level audit log for this type of action.
        current_app.logger.critical(log_description) # Use critical level for dangerous operations

        # --- Perform Deletion ---
        # Note: This does NOT automatically delete related NutrientControllerActivityLogs unless CASCADE is set in DB.
        num_deleted = db.session.query(NutrientController).delete()
        current_app.logger.info(f"Queued deletion for {num_deleted} NutrientController records.")

        # If logs need explicit deletion:
        # num_logs_deleted = db.session.query(NutrientControllerActivityLogs).delete()
        # current_app.logger.info(f"Queued deletion for {num_logs_deleted} associated NutrientControllerActivityLogs records.")

        # --- Commit ---
        db.session.commit()
        current_app.logger.critical(f"Successfully deleted {num_deleted} nutrient controller records (action by {user.email}).")

        return jsonify(message=f"Successfully deleted {num_deleted} nutrient controller records."), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting ALL nutrient controller records (triggered by {deleter_email}): {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred during bulk deletion."}), 500
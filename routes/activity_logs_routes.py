# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\activity_logs_routes.py
import os
from flask import Blueprint, request, jsonify, current_app # Import current_app
from sqlalchemy import text
import traceback  # Import traceback for better error logging
import pytz # For timezone formatting

from db import db
# --- Import ALL referenced Log models ---
from models.activity_logs.admin_activity_logs_model import AdminActivityLogs
from models.activity_logs.greenhouse_activity_logs_model import GreenHouseActivityLogs
from models.activity_logs.hardware_components_activity_logs_model import HardwareComponentActivityLogs
from models.activity_logs.hardware_status_logs_model import HardwareStatusActivityLogs
from models.activity_logs.harvest_activity_logs_model import HarvestActivityLogs
from models.activity_logs.maintenance_activity_logs_model import MaintenanceActivityLogs
from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs
from models.activity_logs.rejection_activity_logs_model import RejectionActivityLogs
from models.activity_logs.sale_activity_log_model import SaleLog
from models.activity_logs.user_activity_logs_model import UserActivityLogs
from models.activity_logs.inventory_log_model import InventoryLog
from models.activity_logs.inventory_container_activity_logs import InventoryContainerLog
from models.activity_logs.planted_crop_activity_logs_model import PlantedCropActivityLogs
from models.activity_logs.inventory_item_logs import InventoryItemLog

# Import needed primary models if relationships are used (Users model)
from models.users_model import Users # Needed for name lookup via relationship

activity_logs_api = Blueprint("activity_logs_api", __name__)

# Load API Key and Timezone
API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace")
PH_TZ = pytz.timezone('Asia/Manila')


# --- Helper Functions ---
def check_api_key(request):
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403
    return None

def format_datetime(dt):
    """Formats datetime consistently to YYYY-MM-DD HH:MM:SS AM/PM using the PH timezone."""
    if not dt: return None
    try:
        if dt.tzinfo is None:
             # Assume naive datetime is in PH time if stored without timezone
             aware_dt = PH_TZ.localize(dt)
        else:
             # Convert any timezone-aware datetime to PH time
             aware_dt = dt.astimezone(PH_TZ)
        # Use %I for 12-hour clock (01-12) and %p for AM/PM
        return aware_dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        current_app.logger.warning(f"Could not format datetime {dt}: {e}")
        return str(dt) # Fallback to string representation

def get_user_name(user_obj):
    """Safely gets user's full name from the User object."""
    if user_obj and isinstance(user_obj, Users):
         # Adjust this based on your actual Users model attributes (e.g., first_name, last_name or just name)
         return f"{getattr(user_obj, 'first_name', '')} {getattr(user_obj, 'last_name', '')}".strip() or getattr(user_obj, 'name', 'Name N/A')
    return "Unknown User"

# --- Routes ---

# --- Admin Logs ---
@activity_logs_api.get("/activity_logs/admin")
def get_all_admin_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = AdminActivityLogs.query.order_by(AdminActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Admin Log data found.", admin_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "name": getattr(log.admin, 'name', 'Unknown Admin') if log.admin else "N/A",
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date) # Use updated format
        } for log in logs]
        return jsonify(admin_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_admin_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500

# --- User Logs ---
@activity_logs_api.get("/activity_logs/user")
def get_all_user_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = UserActivityLogs.query.order_by(UserActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No User Log data found.", user_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "name": get_user_name(log.users),
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date) # Use updated format
        } for log in logs]
        return jsonify(user_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_user_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Greenhouse Logs ---
@activity_logs_api.get("/activity_logs/greenhouse")
def get_all_greenhouse_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = GreenHouseActivityLogs.query.order_by(GreenHouseActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Greenhouse Log data found.", greenhouse_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "greenhouse_id": log.greenhouse_id,
            "name": get_user_name(log.users),
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date) # Use updated format
        } for log in logs]
        return jsonify(greenhouse_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_greenhouse_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Rejection Logs ---
@activity_logs_api.get("/activity_logs/rejection")
def get_all_rejection_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = RejectionActivityLogs.query.order_by(RejectionActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Rejection Log data found.", rejection_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "rejection_id": log.rejection_id,
            "rejected_plant_name": log.reason_for_rejection.plant_name if log.reason_for_rejection else "N/A",
            "name": get_user_name(log.users),
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date) # Use updated format
        } for log in logs]
        return jsonify(rejection_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_rejection_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Hardware Status Logs --- (No user name)
@activity_logs_api.get("/activity_logs/hardware_status")
def get_all_hardware_status_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = HardwareStatusActivityLogs.query.order_by(HardwareStatusActivityLogs.timestamp.desc()).all()
        if not logs: return jsonify(message="No Hardware Status Log data found.", hardware_status_logs=[]), 200
        data = [{
            "log_id": status.log_id,
            "component_id": status.component_id,
            "greenhouse_id": status.greenhouse_id,
            "status": status.status,
            "duration": status.duration,
            "timestamp": format_datetime(status.timestamp), # Use updated format
        } for status in logs]
        return jsonify(hardware_status_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_hardware_status_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Maintenance Logs ---
@activity_logs_api.get("/activity_logs/maintenance")
def get_all_maintenance_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = MaintenanceActivityLogs.query.order_by(MaintenanceActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Maintenance Log data found.", maintenance_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "name": log.name if hasattr(log, 'name') else get_user_name(log.users),
            "maintenance_id": log.maintenance_id,
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date), # Use updated format
        } for log in logs]
        return jsonify(maintenance_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_maintenance_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Harvest Logs ---
@activity_logs_api.get("/activity_logs/harvest")
def get_all_harvest_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = HarvestActivityLogs.query.order_by(HarvestActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Harvest Log data found.", harvest_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "harvest_id": log.harvest_id,
            "harvest_name": log.harvests.name if log.harvests else "N/A",
            "harvested_plant_name": log.harvests.plant_name if log.harvests else "N/A",
            "name": get_user_name(log.users),
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date), # Use updated format
        } for log in logs]
        return jsonify(harvest_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_harvest_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Hardware Components Logs ---
@activity_logs_api.get("/activity_logs/hardware_components")
def get_all_hardware_components_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = HardwareComponentActivityLogs.query.order_by(HardwareComponentActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Hardware Components Log data found.", hardware_component_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "login_id": log.login_id,
            "component_id": log.component_id,
            # --- FIX HERE ---
            "component_name": log.hardware_components.componentName if log.hardware_components else "N/A",
            # --- Use componentName instead of name ---
            "name": get_user_name(log.users),
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date), # Use updated format
        } for log in logs]
        return jsonify(hardware_component_logs=data), 200
    except Exception as e:
        # Log the full traceback for better debugging
        current_app.logger.error(f"Error get_all_hardware_components_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Nutrient Controller Logs --- (No user name)
@activity_logs_api.get("/activity_logs/nutrient_controller")
def get_all_nutrient_controller_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = NutrientControllerActivityLogs.query.order_by(NutrientControllerActivityLogs.logs_date.desc()).all()
        if not logs: return jsonify(message="No Nutrient Controller Log data found.", nutrient_controller_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "controller_id": log.controller_id,
            "greenhouse_id": log.greenhouse_id,
            "activated_by": log.activated_by,
            "logs_description": log.logs_description,
            "logs_date": format_datetime(log.logs_date), # Use updated format
        } for log in logs]
        return jsonify(nutrient_controller_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_nutrient_controller_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Inventory Logs --- (MODIFIED TO MATCH Inventory Item Log Structure)
@activity_logs_api.get("/activity_logs/inventory")
def get_all_inventory_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        # Query InventoryLog table. Need user lookup for 'name'.
        logs = InventoryLog.query.order_by(InventoryLog.timestamp.desc()).all()

        if not logs:
            return jsonify(message="No Inventory Log data found.", inventory_logs=[]), 200

        # Create the response matching the inventory_item_log structure
        data = []
        for log in logs:
            # Fetch the user based on user_id from the log
            user = db.session.get(Users, log.user_id) if log.user_id else None
            data.append({
                "log_id": log.log_id,
                "inventory_id": log.inventory_id, # ID of the related main inventory record
                "user_id": log.user_id,
                "name": get_user_name(user), # Get user name using helper
                "timestamp": format_datetime(log.timestamp),
                "activity_type": log.change_type, # Rename 'change_type' to 'activity_type'
                "description": log.description
            })

        return jsonify(inventory_logs=data), 200

    except Exception as e:
        current_app.logger.error(f"Error get_all_inventory_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error processing inventory logs."}), 500

# DELETE for InventoryLog
@activity_logs_api.delete("/activity_logs/inventory")
def delete_all_inventory_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        num_deleted = db.session.query(InventoryLog).delete(synchronize_session=False) # Use False for performance
        db.session.commit()
        current_app.logger.info(f"Deleted {num_deleted} inventory log records.")
        return jsonify(message=f"All {num_deleted} inventory log records deleted."), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error deleting inventory logs: {e}", exc_info=True)
        return jsonify(error={"message": "Error deleting inventory logs."}), 500


# --- Planted Crop Logs ---
@activity_logs_api.get("/activity_logs/planted_crops")
def get_all_planted_crop_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = PlantedCropActivityLogs.query.order_by(PlantedCropActivityLogs.log_date.desc()).all()
        if not logs: return jsonify(message="No Planted Crop Log data found.", planted_crop_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "plant_id": log.plant_id,
            "plant_name": log.planted_crops.plant_name if log.planted_crops else "N/A",
            "login_id": log.login_id, # This is often the user_id
            "name": get_user_name(log.users),
            "logs_description": log.logs_description,
            "log_date": format_datetime(log.log_date) # Use updated format
        } for log in logs]
        return jsonify(planted_crop_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_planted_crop_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500


# --- Inventory Container Logs --- (MODIFIED TO MATCH Inventory Item Log Structure)
@activity_logs_api.get("/activity_logs/inventory_container")
def get_all_inventory_container_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = InventoryContainerLog.query.order_by(InventoryContainerLog.timestamp.desc()).all()
        if not logs: return jsonify(message="No Inventory Container Log data found.", inventory_container_logs=[]), 200

        # Create response matching inventory_item_log structure
        # NOTE: InventoryContainerLog does NOT store user_id, so 'user_id' and 'name' will be placeholders.
        data = [{
            "log_id": log.log_id,
            "inventory_container_id": log.inventory_container_id, # ID of related container
            "user_id": None, # Placeholder - User ID is not tracked in this log table
            "name": "User N/A", # Placeholder - User Name cannot be determined
            "timestamp": format_datetime(log.timestamp), # Use updated format
            "activity_type": log.change_type, # Rename 'change_type' to 'activity_type'
            "description": log.description,
            # Keep extra relevant fields for this log type
            "item": log.item,
            "old_quantity": int(log.old_quantity) if log.old_quantity is not None else None,
            "new_quantity": int(log.new_quantity) if log.new_quantity is not None else None,
        } for log in logs]

        return jsonify(inventory_container_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_inventory_container_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500

# DELETE for InventoryContainerLog
@activity_logs_api.delete("/activity_logs/inventory_container")
def delete_all_inventory_container_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        num_deleted = db.session.query(InventoryContainerLog).delete(synchronize_session=False) # Use False for performance
        db.session.commit()
        current_app.logger.info(f"Deleted {num_deleted} inventory container log records.")
        return jsonify(message=f"All {num_deleted} inventory container logs deleted."), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error deleting inventory container logs: {e}", exc_info=True)
        return jsonify(error={"message": "Error deleting inventory container logs."}), 500


# --- Sale Logs ---
@activity_logs_api.get("/activity_logs/sale")
def get_all_sale_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        # Assuming SaleLog model has user_id and a relationship named 'users'
        logs = SaleLog.query.order_by(SaleLog.timestamp.desc()).all()
        if not logs: return jsonify(message="No Sale Log data found.", sale_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "sale_id": log.sale_id,
            "user_id": log.user_id if hasattr(log, 'user_id') else log.login_id, # Prefer user_id if exists, else login_id
            "name": get_user_name(log.users),
            "timestamp": format_datetime(log.timestamp), # Use updated format
            "log_message": log.log_message
        } for log in logs]
        return jsonify(sale_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_sale_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500

# DELETE for SaleLog
@activity_logs_api.delete("/activity_logs/sale")
def delete_all_sale_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        num_deleted = db.session.query(SaleLog).delete(synchronize_session=False) # Use False for performance
        db.session.commit()
        current_app.logger.info(f"Deleted {num_deleted} sale log records.")
        return jsonify(message=f"Successfully deleted all {num_deleted} sale log records."), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error deleting sale logs: {e}", exc_info=True)
        return jsonify(error={"message": "Error deleting sale logs."}), 500


# --- Inventory Item Logs Route --- (Target structure)
@activity_logs_api.get("/activity_logs/inventory_item")
def get_all_inventory_item_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        logs = InventoryItemLog.query.order_by(InventoryItemLog.timestamp.desc()).all()
        if not logs: return jsonify(message="No Inventory Item Log data found.", inventory_item_logs=[]), 200
        data = [{
            "log_id": log.log_id,
            "inventory_item_id": log.inventory_item_id, # ID of related inventory item
            "user_id": log.user_id,
            "name": get_user_name(log.users),
            "timestamp": format_datetime(log.timestamp), # Use updated format
            "activity_type": log.activity_type,
            "description": log.description
        } for log in logs]
        return jsonify(inventory_item_logs=data), 200
    except Exception as e:
        current_app.logger.error(f"Error get_all_inventory_item_logs: {e}", exc_info=True)
        return jsonify(error={"message": "Internal server error."}), 500

# DELETE for InventoryItemLog
@activity_logs_api.delete("/activity_logs/inventory_item")
def delete_all_inventory_item_logs():
    api_key_error = check_api_key(request);
    if api_key_error: return api_key_error
    try:
        num_deleted = db.session.query(InventoryItemLog).delete(synchronize_session=False) # Use False for performance
        db.session.commit()
        current_app.logger.info(f"Deleted {num_deleted} inventory item log records.")
        return jsonify(message=f"Successfully deleted all {num_deleted} inventory item log records."), 200
    except Exception as e:
        db.session.rollback(); current_app.logger.error(f"Error deleting inventory item logs: {e}", exc_info=True)
        return jsonify(error={"message": "Error deleting inventory item logs."}), 500
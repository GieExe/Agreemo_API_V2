#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\greenhouses_routes.py
import os
import pytz
from flask import Blueprint, request, jsonify, current_app # Import current_app for logging
from db import db
# Removed unused 'functions' import if 'log_activity' isn't used directly here
from models import ( # Consolidate model imports
    Greenhouse, Users, Harvest, ReasonForRejection,
    HardwareComponents, NutrientController, HardwareCurrentStatus,
    PlantedCrops, InventoryContainer # Added missing models used in DELETE
)
from datetime import datetime
from sqlalchemy.exc import IntegrityError # Import for specific DB errors

# Import all necessary log models
from models.activity_logs.greenhouse_activity_logs_model import GreenHouseActivityLogs
from models.activity_logs.hardware_components_activity_logs_model import HardwareComponentActivityLogs
from models.activity_logs.hardware_status_logs_model import HardwareStatusActivityLogs
from models.activity_logs.harvest_activity_logs_model import HarvestActivityLogs
from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs
from models.activity_logs.planted_crop_activity_logs_model import PlantedCropActivityLogs
from models.activity_logs.rejection_activity_logs_model import RejectionActivityLogs
# UserActivityLogs might not be directly needed here unless logging user actions *on users*

greenhouses_api = Blueprint("greenhouses_api", __name__)

API_KEY = os.environ.get("API_KEY")
PH_TZ = pytz.timezone('Asia/Manila') # Define timezone


# --- Helper Function for Date Formatting ---
def format_datetime(dt):
    """Formats datetime to YYYY-MM-DD HH:MM:SS AM/PM in PH Timezone."""
    if not dt: return None
    try:
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            # If timezone info is missing, assume it's naive but represents PH time
            # Localize it to PH_TZ for correct formatting
            aware_dt = PH_TZ.localize(dt)
        else:
            # If it has timezone info, convert it to PH_TZ
            aware_dt = dt.astimezone(PH_TZ)
        # Format to: Year-Month-Day Hour(12):Minute:Second AM/PM
        return aware_dt.strftime("%Y-%m-%d %I:%M:%S %p")
    except Exception as e:
        # Log the error and return a fallback format
        current_app.logger.warning(f"Could not format datetime {dt}: {e}")
        try:
            return dt.isoformat() # Fallback to ISO format
        except:
            return str(dt) # Final fallback

# --- Helper Function for Logging ---
def log_greenhouse_activity(user_id, greenhouse_id, description):
    """Logs an activity related to a greenhouse."""
    try:
        # Store datetime in UTC or naive, depending on DB config
        # For consistency, let's store naive representing PH time if DB is naive
        # Or store UTC: utc_now = datetime.now(pytz.utc)
        naive_manila_now = datetime.now(PH_TZ).replace(tzinfo=None)
        new_log = GreenHouseActivityLogs(
            login_id=user_id,
            greenhouse_id=greenhouse_id,
            logs_description=description,
            log_date=naive_manila_now # Use naive representation of PH time
        )
        db.session.add(new_log)
        current_app.logger.info(f"Queued greenhouse log: User {user_id}, GH {greenhouse_id}, Desc: {description}")
        return new_log
    except Exception as e:
        current_app.logger.error(f"Failed to create greenhouse log: {e}", exc_info=True)
        raise


# GET all data
@greenhouses_api.get("/greenhouses")
def greenhouses_data():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

        query_data = Greenhouse.query.order_by(Greenhouse.greenhouse_id).all()

        if not query_data:
            return jsonify(message="No greenhouse data found.", greenhouses=[]), 200

        greenhouses_list = [{
            "greenhouse_id": data.greenhouse_id,
            "user_id": data.user_id,
            "name": data.name,
            "location": data.location,
            "size": data.size,
            "climate_type": data.climate_type,
            # Apply the formatting function here
            "created_at": format_datetime(data.created_at),
            "status": data.status # Use string status directly
        } for data in query_data]

        return jsonify(greenhouses=greenhouses_list), 200

    except Exception as e:
        # Corrected the error message from the previous step
        current_app.logger.error(f"Error fetching greenhouses: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# Get specific data by greenhouse_id
@greenhouses_api.get("/greenhouse/<int:greenhouse_id>")
def greenhouse_by_id(greenhouse_id):
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

        greenhouse = db.session.get(Greenhouse, greenhouse_id)

        if greenhouse is None:
            return jsonify(error={"message": f"Greenhouse with ID {greenhouse_id} not found"}), 404

        greenhouse_data = {
            "greenhouse_id": greenhouse.greenhouse_id,
            "user_id": greenhouse.user_id,
            "name": greenhouse.name,
            "location": greenhouse.location,
            "size": greenhouse.size,
            "climate_type": greenhouse.climate_type,
            # Apply the formatting function here
            "created_at": format_datetime(greenhouse.created_at),
            "status": greenhouse.status # Use string status directly
        }

        return jsonify(greenhouse=greenhouse_data), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching greenhouse {greenhouse_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# Add Greenhouse
@greenhouses_api.post("/greenhouse")
def add_greenhouse():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

        # --- Use request.form for adding ---
        email = request.form.get("email")
        name = request.form.get("name")
        location = request.form.get("location")
        size = request.form.get("size")
        climate_type = request.form.get("climate_type")
        status_str = request.form.get("status", "Active") # Default to Active

        # --- Validation ---
        errors = {}
        if not email: errors['email'] = "Required."
        if not name: errors['name'] = "Required."
        allowed_statuses = ["Active", "Inactive"]
        if status_str not in allowed_statuses:
            errors['status'] = f"Invalid status. Must be one of: {', '.join(allowed_statuses)}."
        if errors:
            return jsonify(error={"message": "Missing or invalid fields.", "details": errors}), 400

        # --- Find User ---
        user = Users.query.filter(Users.email.ilike(email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{email}' not found."}), 404

        # --- Prepare Data ---
        # Use naive datetime representing PH time if your DB expects naive
        naive_manila_now = datetime.now(PH_TZ).replace(tzinfo=None)

        # --- Create Greenhouse ---
        new_greenhouse = Greenhouse(
            user_id=user.user_id,
            name=name,
            location=location,
            size=size,
            climate_type=climate_type,
            created_at=naive_manila_now, # Store naive datetime
            status=status_str # Store the validated string
        )
        db.session.add(new_greenhouse)
        db.session.flush()

        # --- Log Activity ---
        log_description = f"Greenhouse '{name}' created by user {user.email}."
        log_greenhouse_activity(user.user_id, new_greenhouse.greenhouse_id, log_description)

        # --- Commit ---
        db.session.commit()
        current_app.logger.info(f"Greenhouse {new_greenhouse.greenhouse_id} created successfully by user {user.email}.")

        # --- Response ---
        # Fetch the newly created record to ensure data is fresh
        created_greenhouse = db.session.get(Greenhouse, new_greenhouse.greenhouse_id)
        return jsonify(
            message="Greenhouse successfully added!",
            greenhouse={
                "greenhouse_id": created_greenhouse.greenhouse_id,
                "user_id": created_greenhouse.user_id,
                "name": created_greenhouse.name,
                "location": created_greenhouse.location,
                "size": created_greenhouse.size,
                "climate_type": created_greenhouse.climate_type,
                # Format the date for the response
                "created_at": format_datetime(created_greenhouse.created_at),
                "status": created_greenhouse.status
            }
        ), 201

    except IntegrityError as e:
         db.session.rollback()
         current_app.logger.error(f"Database integrity error adding greenhouse: {e}", exc_info=True)
         error_detail = str(getattr(e, 'orig', e))
         if "unique constraint" in error_detail.lower() and "name" in error_detail.lower():
              return jsonify(error={"message": f"Greenhouse name '{name}' already exists.", "detail": error_detail}), 409
         return jsonify(error={"message": "Database error adding greenhouse.", "detail": error_detail}), 409

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding greenhouse: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred."}), 500


# --- PATCH ROUTE (Modified to use request.form) ---
@greenhouses_api.patch("/greenhouse/<int:greenhouse_id>")
def update_greenhouse(greenhouse_id):
    """
    Partially updates a greenhouse record using form data.
    Expects form fields for fields to update (name, location, size, climate_type, status)
    and a mandatory 'email' field for logging the user performing the update.
    Requires Content-Type like 'application/x-www-form-urlencoded'.
    """
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

    # --- Use request.form for updating ---
    # Get the mandatory email field first for logging/user check
    email = request.form.get("email")
    if not email:
        return jsonify(error={"message": "Missing required form field: 'email' (for logging)."}), 400

    try:
        user = Users.query.filter(Users.email.ilike(email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{email}' not found."}), 404

        greenhouse = db.session.get(Greenhouse, greenhouse_id)
        if not greenhouse:
            return jsonify(error={"message": f"Greenhouse with ID {greenhouse_id} not found."}), 404

        updated_fields = []
        allowed_updates = ["name", "location", "size", "climate_type", "status"]
        validation_errors = {}

        for field in allowed_updates:
            # Check if the field was included in the form data
            if field in request.form:
                new_value = request.form.get(field) # Get the value from the form
                current_value = getattr(greenhouse, field)

                # Special validation for status
                if field == "status":
                    allowed_statuses = ["Active", "Inactive"]
                    if new_value not in allowed_statuses:
                        validation_errors['status'] = f"Invalid status. Must be one of: {', '.join(allowed_statuses)}."
                        continue # Skip this field if validation fails

                # Check if the new value is actually different from the current one
                # Note: This treats an empty string "" from the form as a valid update
                # if the current value wasn't already "". Consider if you want this behavior.
                if new_value != current_value:
                    setattr(greenhouse, field, new_value)
                    updated_fields.append(f"{field} changed to '{new_value}'")

        if validation_errors:
             return jsonify(error={"message": "Validation failed.", "details": validation_errors}), 400

        if not updated_fields:
             # Fetch fresh data before returning
             current_greenhouse = db.session.get(Greenhouse, greenhouse_id)
             return jsonify(
                 message="No changes detected or applied.",
                 greenhouse={
                     "greenhouse_id": current_greenhouse.greenhouse_id,
                     "user_id": current_greenhouse.user_id,
                     "name": current_greenhouse.name,
                     "location": current_greenhouse.location,
                     "size": current_greenhouse.size,
                     "climate_type": current_greenhouse.climate_type,
                     "created_at": format_datetime(current_greenhouse.created_at),
                     "status": current_greenhouse.status
                 }
             ), 200

        # --- Log Activity ---
        log_description = f"Greenhouse '{greenhouse.name}' (ID: {greenhouse_id}) updated by {user.email}. Changes: {'; '.join(updated_fields)}."
        log_greenhouse_activity(user.user_id, greenhouse_id, log_description)

        # --- Commit ---
        db.session.commit()
        current_app.logger.info(f"Greenhouse {greenhouse_id} updated successfully by user {user.email}.")

        # --- Response ---
        # Fetch fresh data after commit
        updated_greenhouse = db.session.get(Greenhouse, greenhouse_id)
        return jsonify(
            message="Greenhouse updated successfully.",
            greenhouse={
                 "greenhouse_id": updated_greenhouse.greenhouse_id,
                 "user_id": updated_greenhouse.user_id,
                 "name": updated_greenhouse.name,
                 "location": updated_greenhouse.location,
                 "size": updated_greenhouse.size,
                 "climate_type": updated_greenhouse.climate_type,
                 "created_at": format_datetime(updated_greenhouse.created_at),
                 "status": updated_greenhouse.status
            }
        ), 200

    except IntegrityError as e:
         db.session.rollback()
         current_app.logger.error(f"Database integrity error updating greenhouse {greenhouse_id}: {e}", exc_info=True)
         error_detail = str(getattr(e, 'orig', e))
         # Check if the 'name' field was part of the form data causing the error
         updated_name = request.form.get("name")
         if updated_name and "unique constraint" in error_detail.lower() and "name" in error_detail.lower():
              return jsonify(error={"message": f"Greenhouse name '{updated_name}' already exists.", "detail": error_detail}), 409
         return jsonify(error={"message": "Database error updating greenhouse.", "detail": error_detail}), 409

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating greenhouse {greenhouse_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred during update."}), 500


# --- DELETE Routes (No changes needed for date formatting) ---
@greenhouses_api.delete("/greenhouse/<int:greenhouse_id>")
def delete_greenhouse(greenhouse_id):
    # ... (existing DELETE logic) ...
    # Add logging before commit if desired
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

        email = request.form.get("email")
        if not email:
            return jsonify(error={"message": "Missing required form field: 'email' (for logging)."}), 400

        user = Users.query.filter(Users.email.ilike(email)).first()
        if not user:
            return jsonify(error={"message": f"User with email '{email}' not found."}), 404

        greenhouse = db.session.get(Greenhouse, greenhouse_id)
        if not greenhouse:
            return jsonify(error={"message": f"Greenhouse with ID {greenhouse_id} not found"}), 404

        greenhouse_name_ref = greenhouse.name

        # --- Delete associated records (CASCADE might be better handled by DB constraints) ---
        # Using synchronize_session=False for potentially better performance, but be careful
        # if you have complex session state management. 'fetch' is safer but slower.
        current_app.logger.info(f"Beginning deletion cascade for Greenhouse ID {greenhouse_id}...")

        # Logs first
        PlantedCropActivityLogs.query.filter(PlantedCropActivityLogs.plant_id.in_(
            db.session.query(PlantedCrops.plant_id).filter_by(greenhouse_id=greenhouse_id)
        )).delete(synchronize_session=False)
        HarvestActivityLogs.query.filter(HarvestActivityLogs.harvest_id.in_(
            db.session.query(Harvest.harvest_id).filter_by(greenhouse_id=greenhouse_id)
        )).delete(synchronize_session=False)
        RejectionActivityLogs.query.filter(RejectionActivityLogs.rejection_id.in_(
            db.session.query(ReasonForRejection.rejection_id).filter_by(greenhouse_id=greenhouse_id)
        )).delete(synchronize_session=False)
        HardwareComponentActivityLogs.query.filter(HardwareComponentActivityLogs.component_id.in_(
             db.session.query(HardwareComponents.component_id).filter_by(greenhouse_id=greenhouse_id)
        )).delete(synchronize_session=False)
        NutrientControllerActivityLogs.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        HardwareStatusActivityLogs.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        GreenHouseActivityLogs.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        current_app.logger.debug(f"Associated logs queued for deletion for GH {greenhouse_id}.")

        # Then dependent data tables
        PlantedCrops.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        Harvest.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        ReasonForRejection.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        HardwareCurrentStatus.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        HardwareComponents.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        NutrientController.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        InventoryContainer.query.filter_by(greenhouse_id=greenhouse_id).delete(synchronize_session=False)
        current_app.logger.debug(f"Associated data tables queued for deletion for GH {greenhouse_id}.")


        # --- Delete the Greenhouse ---
        db.session.delete(greenhouse)
        current_app.logger.info(f"Queued deletion for Greenhouse ID {greenhouse_id} ('{greenhouse_name_ref}') itself.")

        # --- Log Deletion Action ---
        log_description = f"Greenhouse '{greenhouse_name_ref}' (ID: {greenhouse_id}) and all associated data deleted by user {user.email}."
        log_greenhouse_activity(user.user_id, greenhouse_id, log_description)


        # --- Commit Transaction ---
        db.session.commit()
        current_app.logger.info(f"Successfully committed deletion of Greenhouse ID {greenhouse_id} by user {user.email}.")

        return jsonify(message=f"Successfully deleted greenhouse '{greenhouse_name_ref}' (ID: {greenhouse_id}) and its associated records/logs."), 200

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Integrity error deleting greenhouse {greenhouse_id}: {e}", exc_info=True)
        error_detail = str(getattr(e, 'orig', e))
        return jsonify(error={"message": "Cannot delete greenhouse due to existing database references that were not cascade deleted.", "detail": error_detail}), 409

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting greenhouse {greenhouse_id}: {e}", exc_info=True)
        return jsonify(error={"message": "An internal server error occurred during deletion."}), 500


@greenhouses_api.delete("/greenhouses")
def delete_all_greenhouses():
    # ... (keep existing DELETE ALL logic, no date formatting needed here) ...
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Incorrect api_key."}), 403

        # Optional: Require confirmation parameter ?confirm=true
        confirm = request.args.get("confirm", "false").lower() == "true"
        if not confirm:
             return jsonify(error={"message": "Bulk deletion requires confirmation. Add '?confirm=true' to the URL."}), 400

        current_app.logger.warning("Initiating DELETE ALL GREENHOUSES operation.")

        # Delete in order reverse of dependencies, or rely on CASCADE if configured
        # Using synchronize_session=False for performance in bulk deletes
        PlantedCropActivityLogs.query.delete(synchronize_session=False)
        HarvestActivityLogs.query.delete(synchronize_session=False)
        RejectionActivityLogs.query.delete(synchronize_session=False)
        HardwareComponentActivityLogs.query.delete(synchronize_session=False)
        NutrientControllerActivityLogs.query.delete(synchronize_session=False)
        HardwareStatusActivityLogs.query.delete(synchronize_session=False)
        GreenHouseActivityLogs.query.delete(synchronize_session=False)

        PlantedCrops.query.delete(synchronize_session=False)
        Harvest.query.delete(synchronize_session=False)
        ReasonForRejection.query.delete(synchronize_session=False)
        HardwareCurrentStatus.query.delete(synchronize_session=False)
        HardwareComponents.query.delete(synchronize_session=False)
        NutrientController.query.delete(synchronize_session=False)
        InventoryContainer.query.delete(synchronize_session=False)

        num_deleted = Greenhouse.query.delete(synchronize_session=False)

        db.session.commit()
        current_app.logger.warning(f"COMMITTED deletion of {num_deleted} greenhouses and all associated data.")

        return jsonify(message=f"Successfully deleted {num_deleted} greenhouse(s) along with all associated records and logs."), 200

    except IntegrityError as e:
        db.session.rollback()
        current_app.logger.error(f"Integrity error during bulk greenhouse deletion: {e}", exc_info=True)
        error_detail = str(getattr(e, 'orig', e))
        return jsonify(error={"message": "Cannot delete all greenhouses due to existing database references.", "detail": error_detail}), 409

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting all greenhouses: {e}", exc_info=True)
        return jsonify(error={"message": "An error occurred during bulk deletion."}), 500
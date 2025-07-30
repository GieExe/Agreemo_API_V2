# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\inventory_item_routes.py
import os
import pytz
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

from db import db
from models.inventory_items import InventoryItem # Assumes this model now has user_id
from models.activity_logs.inventory_item_logs import InventoryItemLog
from models.users_model import Users  # Import User model
# Assuming greenhouses_model exists and is needed for validation
from models.greenhouses_model import Greenhouse

inventory_item_api = Blueprint("inventory_item_api", __name__)

# It's generally better practice to load sensitive keys from config or environment variables
# Ensure API_KEY is set in your environment for production
API_KEY = os.environ.get("API_KEY", "default_api_key_please_replace")
PH_TZ = pytz.timezone('Asia/Manila')


# --- Helper Functions ---

def log_inventory_item_activity(item_id, user_id, activity_type, description):
    """Logs an inventory item activity."""
    try:
        # Use UTC for consistency in the database, convert to local time for display if needed
        utc_now = datetime.now(pytz.utc)

        new_log = InventoryItemLog(
            inventory_item_id=item_id,
            user_id=user_id,
            timestamp=utc_now, # Log in UTC
            activity_type=activity_type,
            description=description
        )
        db.session.add(new_log)
        db.session.flush()  # Ensures log gets an ID if needed before commit
        current_app.logger.info(f"InventoryItemLog created: {description} by User ID: {user_id}")
        return new_log
    except Exception as e:
        # Use current_app.logger for consistency
        current_app.logger.error(f"Error creating InventoryItemLog: {e}", exc_info=True)
        # Don't raise here unless the calling function absolutely needs to stop
        # Let the main route handle the overall transaction rollback
        return None # Indicate failure


# --- Routes ---

@inventory_item_api.get("/inventory_items")
def get_all_inventory_items():
    """Retrieves all inventory items."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(
            error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

    try:
        items = InventoryItem.query.order_by(InventoryItem.inventory_item_id).all() # Added ordering

        item_list = []
        for item in items:
            # Format date to PH Timezone for display
            date_received_display = None
            if item.date_received:
                # Ensure the stored datetime is treated as UTC if naive, then convert to PH Time
                if item.date_received.tzinfo is None:
                    date_received_utc = pytz.utc.localize(item.date_received)
                else:
                    date_received_utc = item.date_received.astimezone(pytz.utc)

                date_received_ph = date_received_utc.astimezone(PH_TZ)
                # --- MODIFIED FORMAT TO MATCH LOGS ---
                date_received_display = date_received_ph.strftime("%Y-%m-%d %I:%M:%S %p")

            item_list.append({
                "inventory_item_id": item.inventory_item_id,
                "user_id": item.user_id, # This should now work correctly
                "greenhouse_id": item.greenhouse_id,
                "item_name": item.item_name,
                "item_count": item.item_count,
                "unit": item.unit,
                "description": item.description,
                "price": float(item.price) if item.price is not None else 0.0,
                "total_price": float(item.total_price) if item.total_price is not None else 0.0,
                "date_received": date_received_display, # Use the newly formatted string
                # Optionally add user details if needed via relationship:
                # "user_email": item.user.email if item.user else None
            })

        return jsonify(inventory_items=item_list), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching inventory items: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE
        return jsonify(error={"message": f"Error fetching inventory items: {str(e)}"}), 500


@inventory_item_api.get("/inventory_items/<int:item_id>")
def get_inventory_item_by_id(item_id):
    """Retrieves a specific inventory item by ID."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(
            error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

    try:
        item = db.session.get(InventoryItem, item_id) # Use session.get for primary key lookup
        if not item:
            return jsonify(error={"message": "Inventory item not found."}), 404

        # Format date to PH Timezone for display
        date_received_display = None
        if item.date_received:
            # Ensure the stored datetime is treated as UTC if naive, then convert to PH Time
            if item.date_received.tzinfo is None:
                 date_received_utc = pytz.utc.localize(item.date_received)
            else:
                 date_received_utc = item.date_received.astimezone(pytz.utc)

            date_received_ph = date_received_utc.astimezone(PH_TZ)
            # --- MODIFIED FORMAT TO MATCH LOGS ---
            date_received_display = date_received_ph.strftime("%Y-%m-%d %I:%M:%S %p")

        item_data = {
            "inventory_item_id": item.inventory_item_id,
            "user_id": item.user_id, # This should now work correctly
            "greenhouse_id": item.greenhouse_id,
            "item_name": item.item_name,
            "item_count": item.item_count,
            "unit": item.unit,
            "description": item.description,
            "price": float(item.price) if item.price is not None else 0.0,
            "total_price": float(item.total_price) if item.total_price is not None else 0.0,
            "date_received": date_received_display, # Use the newly formatted string
             # Optionally add user details if needed via relationship:
             # "user_email": item.user.email if item.user else None
        }

        return jsonify(inventory_item=item_data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching inventory item {item_id}: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE
        return jsonify(error={"message": f"Error fetching inventory item {item_id}: {str(e)}"}), 500


@inventory_item_api.post("/inventory_items")
def create_inventory_item():
    """Creates a new inventory item, using user_email to find user_id."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(
            error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

    # Use request.form for form data
    data = request.form
    user_email = data.get("user_email")
    item_name = data.get("item_name")
    item_count_str = data.get("item_count")
    unit = data.get("unit")
    description = data.get("description") # Optional
    price_str = data.get("price")
    date_received_str = data.get("date_received") # Optional, format YYYY-MM-DD
    greenhouse_id_str = data.get("greenhouse_id")

    # --- Validation ---
    errors = {}
    if not user_email: errors["user_email"] = "User email is required."
    if not item_name: errors["item_name"] = "Item name is required."
    if not item_count_str: errors["item_count"] = "Item count is required."
    if not unit: errors["unit"] = "Unit is required."
    if not price_str: errors["price"] = "Price is required."
    if not greenhouse_id_str: errors["greenhouse_id"] = "Greenhouse ID is required."

    if errors:
        return jsonify(error={"message": "Validation failed.", "errors": errors}), 400

    # Further validation and type conversion
    item_count = None
    price = None
    greenhouse_id = None
    date_received = None
    user_id = None # Initialize user_id

    try:
        item_count = int(item_count_str)
        if item_count < 0: errors["item_count"] = "Item count must be non-negative."

        price = float(price_str)
        if price < 0: errors["price"] = "Price must be non-negative."

        greenhouse_id = int(greenhouse_id_str)
        # No need to check < 0 for IDs usually, depends on schema

        if date_received_str:
            try:
                # Expecting YYYY-MM-DD format from input
                date_received_naive = datetime.strptime(date_received_str, "%Y-%m-%d")
                # Localize to PH timezone then convert to UTC for storage
                date_received = PH_TZ.localize(date_received_naive).astimezone(pytz.utc)
            except ValueError:
                errors["date_received"] = "Invalid date format. Use YYYY-MM-DD."
        else:
            # Default to now in UTC if not provided
            date_received = datetime.now(pytz.utc)

        # Find User by Email
        user = Users.query.filter(Users.email.ilike(user_email)).first() # Case-insensitive search
        if not user:
            errors["user_email"] = f"User not found with email: {user_email}"
        else:
            user_id = user.user_id # Get the user_id

        # Validate Greenhouse existence
        greenhouse = db.session.get(Greenhouse, greenhouse_id) # Use session.get for primary key
        if not greenhouse:
            errors["greenhouse_id"] = f"Greenhouse not found with ID: {greenhouse_id}"

    except ValueError as e:
        # Catches errors from int() or float()
        return jsonify(error={"message": f"Invalid numeric format: check item_count, price, or greenhouse_id. Details: {str(e)}"}), 400
    except Exception as e:
        # Catch potential timezone or other unexpected errors during validation
        current_app.logger.error(f"Error during validation/conversion: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE (for validation stage)
        return jsonify(error={"message": f"An error occurred during data validation: {str(e)}"}), 400


    if errors:
         return jsonify(error={"message": "Validation failed.", "errors": errors}), 400

    # --- Create Item ---
    try:
        # Calculate total price
        total_price = item_count * price

        # Create the item - Pass the datetime object directly
        new_item = InventoryItem(
            user_id=user_id, # Use the retrieved user_id
            greenhouse_id=greenhouse_id,
            item_name=item_name,
            item_count=item_count,
            unit=unit,
            description=description,
            price=price,
            total_price=total_price,
            date_received=date_received # Pass the timezone-aware datetime object
        )

        db.session.add(new_item)
        db.session.flush()  # Get item_id before logging

        # Log activity (make sure user_id is available)
        log_inventory_item_activity(
            item_id=new_item.inventory_item_id,
            user_id=user_id, # Pass the retrieved user_id
            activity_type="create",
            description=f"Created inventory item: '{item_name}' (Count: {item_count})"
        )

        db.session.commit()

        # Return the ID of the newly created item
        return jsonify(message="Inventory item created successfully.", inventory_item_id=new_item.inventory_item_id), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating inventory item in database: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE
        return jsonify(error={"message": f"Error creating inventory item in database: {str(e)}"}), 500


@inventory_item_api.put("/inventory_items/<int:item_id>")
def update_inventory_item(item_id):
    """Updates an existing inventory item."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(
            error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

    # Find the item first to avoid unnecessary work if it doesn't exist
    try:
        item = db.session.get(InventoryItem, item_id) # Use session.get
        if not item:
            return jsonify(error={"message": "Inventory item not found."}), 404
    except Exception as e:
         current_app.logger.error(f"Error fetching item {item_id} for update: {e}", exc_info=True)
         # MODIFIED ERROR MESSAGE (during initial fetch)
         return jsonify(error={"message": f"Error fetching item {item_id} for update: {str(e)}"}), 500

    # Get data from form - use .get() to allow partial updates
    data = request.form
    user_email = data.get("user_email") # User performing the update OR changing ownership
    item_name = data.get("item_name")
    item_count_str = data.get("item_count")
    unit = data.get("unit")
    description = data.get("description")
    price_str = data.get("price")
    date_received_str = data.get("date_received") # Format YYYY-MM-DD
    greenhouse_id_str = data.get("greenhouse_id")

    # --- Validation and Update ---
    errors = {}
    updated_fields = [] # Track changes for logging
    user_id_performing_update = None # ID of user making the request

    # Find the user making the request (needed for logging)
    if user_email:
        try:
            updater_user = Users.query.filter(Users.email.ilike(user_email)).first()
            if not updater_user:
                 errors["user_email"] = f"User performing update not found with email: {user_email}"
            else:
                 user_id_performing_update = updater_user.user_id
        except Exception as e:
             current_app.logger.error(f"Error looking up user {user_email} during update: {e}", exc_info=True)
             # MODIFIED ERROR MESSAGE (during user lookup)
             return jsonify(error={"message": f"Error looking up user '{user_email}': {str(e)}"}), 500
    else:
        # Maybe require user_email for updates or fetch from session/token if authenticated
        errors["user_email"] = "User email (of the updater) is required for updates."
        # Return early if updater email is required and missing
        return jsonify(error={"message": "Validation failed during update.", "errors": errors}), 400


    # Apply updates if data is provided
    try:
        if item_name is not None:
            if item_name != item.item_name:
                item.item_name = item_name
                updated_fields.append(f"name to '{item_name}'")
        if item_count_str is not None:
            item_count = int(item_count_str)
            if item_count < 0: errors["item_count"] = "Item count must be non-negative."
            elif item.item_count != item_count:
                item.item_count = item_count
                updated_fields.append(f"count to {item_count}")
        if unit is not None:
             if item.unit != unit:
                item.unit = unit
                updated_fields.append(f"unit to '{unit}'")
        # Allow setting description to empty string or null if needed
        if description is not None:
             if item.description != description:
                item.description = description if description else None # Handle empty string -> None
                updated_fields.append(f"description")
        if price_str is not None:
            price = float(price_str)
            if price < 0: errors["price"] = "Price must be non-negative."
            elif item.price != price:
                item.price = price
                updated_fields.append(f"price to {price}")
        if date_received_str is not None:
            try:
                date_received_naive = datetime.strptime(date_received_str, "%Y-%m-%d")
                date_received_utc = PH_TZ.localize(date_received_naive).astimezone(pytz.utc)
                # Get the stored date_received, ensure it's timezone-aware UTC for comparison
                stored_date_utc = None
                if item.date_received:
                    if item.date_received.tzinfo is None:
                         stored_date_utc = pytz.utc.localize(item.date_received)
                    else:
                         stored_date_utc = item.date_received.astimezone(pytz.utc)

                # Compare full datetime:
                if stored_date_utc != date_received_utc:
                    item.date_received = date_received_utc
                    updated_fields.append(f"date received to {date_received_str}")
            except ValueError:
                errors["date_received"] = "Invalid date format. Use YYYY-MM-DD."

        if greenhouse_id_str is not None:
             greenhouse_id = int(greenhouse_id_str)
             if item.greenhouse_id != greenhouse_id:
                greenhouse = db.session.get(Greenhouse, greenhouse_id) # Use session.get
                if not greenhouse:
                     errors["greenhouse_id"] = f"Greenhouse not found with ID: {greenhouse_id}"
                else:
                     item.greenhouse_id = greenhouse_id
                     updated_fields.append(f"greenhouse ID to {greenhouse_id}")

        # Recalculate total price if count or price changed
        # Use list comprehension for cleaner check
        if any(field_update.startswith(prefix) for field_update in updated_fields for prefix in ["count to", "price to"]):
             item.total_price = (item.item_count or 0) * (item.price or 0)
             # Check if already logged explicitly before adding implicit log
             if not any(field_update.startswith("total price") for field_update in updated_fields):
                  updated_fields.append("total price recalculated")

    except ValueError as ve:
         # Catches errors from int() or float() during update attempt
         return jsonify(error={"message": f"Invalid numeric format in update data: {str(ve)}"}), 400
    except Exception as e:
         current_app.logger.error(f"Error during update value processing: {e}", exc_info=True)
         # MODIFIED ERROR MESSAGE (during update processing)
         return jsonify(error={"message": f"Error during update data processing: {str(e)}"}), 500


    if errors:
        return jsonify(error={"message": "Validation failed during update.", "errors": errors}), 400

    if not updated_fields:
        return jsonify(message="No changes detected.", item_id=item_id), 200 # Or 304 Not Modified

    # --- Commit Update and Log ---
    try:
        # Log activity using the ID of the user who performed the update
        log_description = f"Updated inventory item '{item.item_name}' (ID: {item_id}). Changes: {', '.join(updated_fields)}."
        log_inventory_item_activity(
            item_id=item.inventory_item_id,
            user_id=user_id_performing_update, # Use the updater's ID
            activity_type="update",
            description=log_description
        )

        db.session.commit()

        return jsonify(message="Inventory item updated successfully.", item_id=item.inventory_item_id), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating inventory item {item_id} in database: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE
        return jsonify(error={"message": f"Error committing update for item {item_id}: {str(e)}"}), 500


@inventory_item_api.delete("/inventory_items/<int:item_id>")
def delete_inventory_item(item_id):
    """Deletes an inventory item."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(
            error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

    # It's good practice to know WHO deleted the item.
    user_email = request.form.get("user_email")
    if not user_email:
         # If using authentication, get user ID from the session/token instead.
         return jsonify(error={"message": "User email (of the user performing deletion) is required in the request form data."}), 400

    user_id_performing_delete = None
    try:
        user = Users.query.filter(Users.email.ilike(user_email)).first()
        if not user:
            return jsonify(error={"message": f"User performing deletion not found with email: {user_email}"}), 404
        user_id_performing_delete = user.user_id
    except Exception as e:
        current_app.logger.error(f"Error looking up user {user_email} during delete: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE (during user lookup)
        return jsonify(error={"message": f"Error looking up user '{user_email}': {str(e)}"}), 500

    try:
        item = db.session.get(InventoryItem, item_id) # Use session.get
        if not item:
            return jsonify(error={"message": "Inventory item not found."}), 404

        item_name_before_delete = item.item_name # Keep for logging
        associated_user_id = item.user_id # Keep for logging if needed

        # Log activity BEFORE deleting
        log_description = f"Deleted inventory item: '{item_name_before_delete}' (ID: {item_id}, originally associated with User ID: {associated_user_id})."
        log_inventory_item_activity(
            item_id=item_id, # Use the ID directly
            user_id=user_id_performing_delete, # User who initiated delete
            activity_type="delete",
            description=log_description
        )

        # Consider related data: Should deleting an item delete its logs?
        # SQLAlchemy cascading might handle this if configured, otherwise manual cleanup needed.
        # Example: Delete related logs explicitly if cascade isn't set
        # InventoryItemLog.query.filter_by(inventory_item_id=item_id).delete(synchronize_session=False) # Use False for performance

        db.session.delete(item)
        db.session.commit()

        return jsonify(message="Inventory item deleted successfully."), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting inventory item {item_id}: {e}", exc_info=True)
        # MODIFIED ERROR MESSAGE
        return jsonify(error={"message": f"Error deleting item {item_id}: {str(e)}"}), 500
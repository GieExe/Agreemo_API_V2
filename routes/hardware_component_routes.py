# C:\Users\Giebert\PycharmProjects\agreemo_api\routes\hardware_component_routes.py
import datetime
import os
import pytz
from flask import Blueprint, request, jsonify, current_app  # Import current_app
from datetime import datetime # Keep only one datetime import
from db import db
from functions import log_activity # Assuming this function exists elsewhere if needed
from models import HardwareComponents, Greenhouse, Users
from models.activity_logs.hardware_components_activity_logs_model import HardwareComponentActivityLogs
from models.activity_logs.hardware_status_logs_model import HardwareStatusActivityLogs # Keep if used elsewhere
import psycopg2  # import
import json  # import


hardware_components_api = Blueprint("hardware_components_api", __name__)

API_KEY = os.environ.get("API_KEY")

# Create method trigger:
def send_hardware_component_notification(payload):  # Pass to trigger new change
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']  # Config
    try:
        conn = psycopg2.connect(db_uri)  # new Connection.
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:  # Handle by with wrapper for the cursor.
            curs.execute(f"NOTIFY hardware_components_updates, %s;", (json.dumps(payload),))  # Trigger New Change
        conn.close()  # CLose Connectino
    except psycopg2.Error as e:  # Error checking
        print(f"Sending hardware component notification error : {e}") # Corrected print message

#Added send method for hardware_components : Listener name consistent on Postgrest  Channel. postgress. Listen/notification channel,. logs: name
def send_hardware_components_logs_notification(payload):  # Add method `notificaton logs table:., harvest activity changes ,/sent and: callback,. to listen,.: using instances , harvest
    """Sends a notification for hardware components activity log updates."""
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI'] # sent and make it and harvest activity changes., in table: data : `changes in logs, sent.
    try:  # try/except/ Best Handling /Exceptions,.. database connection or related : , check issue,. problems./ checking via,. checking if error issue logs ` and other bugs report.`.,`
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:#,. Create : and Cursor is `Wrapper in with, ` statment it, safe /clean: to call. safely, on cursor best  in method rather use outside ,best practice/better
            curs.execute(f"NOTIFY hardware_components_logs_updates, %s;", (json.dumps(payload),)) # Trigger the NOtifiy
        conn.close() # Close connection , close if after,. ` trigger/ sent update data,. using: postgrest socket: ` : changes: record and

    except psycopg2.Error as e:# Exception handling. and catch connection issue /etc,..  and: error raise to this Logs debuggs and debugging via check issue., . ` related /error/. problems
        print(f"Error sending hardware components activity log notification: {e}")#logs report during trigger connection issues..

@hardware_components_api.get("/hardware_components")
def hardware_component_data():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed.  Make sure you have the correct api_key."}), 403

        query_data = HardwareComponents.query.all()

        if not query_data:
            return jsonify(message="No hardware component data found."), 404

        hardware_component_dict = [{
            "component_id": data.component_id,
            "greenhouse_id": data.greenhouse_id,
            "componentName": data.componentName,
            "date_of_installation": data.date_of_installation.isoformat() if data.date_of_installation else None, # Format date
            "manufacturer": data.manufacturer,
            "model_number": data.model_number,
            "serial_number": data.serial_number
        } for data in query_data]

        return jsonify(hardware_component_dict), 200

    except Exception as e:
        # Log the exception for debugging
        current_app.logger.error(f"Error fetching hardware components: {e}")
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500

# add for developer use only
@hardware_components_api.post("/hardware_components/add")
def hardware_components_add():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

        # Use request.json if sending JSON data, or request.form for form data
        data = request.get_json() if request.is_json else request.form

        greenhouse_id = data.get("greenhouse_id")
        if not greenhouse_id:
             return jsonify(error={"message": "greenhouse_id is required."}), 400

        greenhouse = Greenhouse.query.get(greenhouse_id)
        if not greenhouse:
            return jsonify(error={"message": f"Greenhouse with id {greenhouse_id} not found!"}), 404

        email = data.get("email")
        if not email:
            return jsonify(error={"message": "email is required."}), 400

        user = Users.query.filter_by(email=email).first()
        if not user:
            return jsonify(error={"message": f"User with email {email} not found."}), 404

        componentName = data.get("componentName")
        manufacturer = data.get("manufacturer")
        model_number = data.get("model_number")
        serial_number = data.get("serial_number")

        # Basic validation for required fields
        if not all([componentName, manufacturer, model_number, serial_number]):
             return jsonify(error={"message": "Missing required fields: componentName, manufacturer, model_number, serial_number"}), 400


        ph_tz = pytz.timezone('Asia/Manila')
        manila_now = datetime.now(ph_tz)
        naive_manila_now = manila_now.replace(tzinfo=None)  # Convert to naive datetime

        new_hardware_components = HardwareComponents(
            user_id = user.user_id,
            greenhouse_id = greenhouse_id,
            componentName = componentName,
            manufacturer = manufacturer,
            model_number = model_number,
            serial_number = serial_number,
            date_of_installation = naive_manila_now, # Already naive
        )

        db.session.add(new_hardware_components)
        # Commit here to get the component_id for the log, handle potential errors
        try:
            db.session.flush() # Flush to get the ID without full commit yet

            # --- Create Log --- #
            new_hardware_components_activity_logs = HardwareComponentActivityLogs(
                login_id=user.user_id, # Changed from login_id to user_id for consistency? Check your model
                component_id=new_hardware_components.component_id, # Use the flushed ID
                logs_description=f'New Hardware Component "{componentName}" successfully added.',
                log_date=naive_manila_now # Use the same timestamp
            )
            db.session.add(new_hardware_components_activity_logs)

            # --- Final Commit --- #
            db.session.commit() # Commit both component and log together

            # --- Send Notifications (After successful commit) --- #
            try:
                send_hardware_component_notification({
                    "action": "insert",
                    "component_id": new_hardware_components.component_id,
                     # Optionally include more data if needed by listeners
                    "componentName": componentName,
                    "greenhouse_id": greenhouse_id
                })
                send_hardware_components_logs_notification({
                     "action": "insert",
                     "log_id": new_hardware_components_activity_logs.log_id,
                     # Optionally include more data
                     "component_id": new_hardware_components.component_id,
                     "description": new_hardware_components_activity_logs.logs_description
                })
            except Exception as notify_err:
                # Log notification error but don't fail the request
                current_app.logger.error(f"Failed to send notifications after adding component {new_hardware_components.component_id}: {notify_err}")


            return jsonify(
                message="Hardware Component successfully added!",
                component_id=new_hardware_components.component_id # Return the new ID
                ), 201

        except Exception as e_inner: # Catch commit errors
            db.session.rollback() # Rollback on inner error
            current_app.logger.error(f"Database error adding hardware component: {e_inner}")
            return jsonify(error={"Message": f"Failed to add hardware component due to database error: {str(e_inner)}"}), 500


    except Exception as e: # Catch outer errors (like JSON parsing, initial checks)
        db.session.rollback() # Ensure rollback on any failure
        current_app.logger.error(f"Error in add hardware component request: {e}")
        return jsonify(error={"Message": f"Failed to process add request. Error: {str(e)}"}), 500


# ---- NEW DELETE ROUTE ----
@hardware_components_api.delete("/hardware_components/delete/<int:component_id>")
def delete_hardware_component(component_id):
    """
    Deletes a hardware component and its associated activity logs.
    Requires component_id in the URL path.
    """
    try:
        # 1. Authorization Check
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

        # 2. Find the Component
        component_to_delete = HardwareComponents.query.get(component_id)
        if not component_to_delete:
            return jsonify(error={"message": f"Hardware Component with id {component_id} not found."}), 404

        # Store name for notification before deletion
        deleted_component_name = component_to_delete.componentName

        # 3. Find and Delete Associated Logs FIRST
        # Use .delete(synchronize_session=False) for potentially better performance on bulk deletes
        # though iterating might be clearer if specific logic per log is needed later.
        logs_deleted_count = HardwareComponentActivityLogs.query.filter_by(component_id=component_id).delete(synchronize_session='fetch')
        # 'fetch' strategy re-evaluates the session state after delete, 'evaluate' assumes state matches. 'False' can be faster but less safe if session is complex.

        # 4. Delete the Component
        db.session.delete(component_to_delete)

        # 5. Commit the transaction
        db.session.commit()

        # 6. Send Notification (After successful commit)
        try:
            send_hardware_component_notification({
                "action": "delete",
                "component_id": component_id,
                "componentName": deleted_component_name # Send name for context
            })
            # Optional: Notify about log deletion? Usually not needed unless specifically required.
            # send_hardware_components_logs_notification({
            #     "action": "delete_bulk",
            #     "component_id": component_id,
            #     "deleted_count": logs_deleted_count
            # })
        except Exception as notify_err:
             # Log notification error but don't fail the request
            current_app.logger.error(f"Failed to send notification after deleting component {component_id}: {notify_err}")


        return jsonify(message=f"Hardware Component '{deleted_component_name}' (ID: {component_id}) and {logs_deleted_count} associated logs successfully deleted."), 200

    except Exception as e:
        # 7. Error Handling with Rollback
        db.session.rollback() # Important: Undo changes if anything fails
        current_app.logger.error(f"Error deleting hardware component {component_id}: {e}")
        return jsonify(error={"Message": f"Failed to delete hardware component. Error: {str(e)}"}), 500

# --- You might need to register the blueprint in your main app factory ---
# Example in your app/__init__.py or wherever you create the app:
# from .routes.hardware_component_routes import hardware_components_api
# app.register_blueprint(hardware_components_api, url_prefix='/api') # Or your desired prefix
# C:\Users\Giebert\PycharmProjects\agreemo_api\routes\maintenance_routes.py
import os
from flask import Blueprint, request, jsonify, current_app
from db import db
from models import Maintenance, Users
from datetime import datetime
import pytz
from models.activity_logs.maintenance_activity_logs_model import MaintenanceActivityLogs
import psycopg2
import json

maintenance_api = Blueprint("maintenance_api", __name__)

API_KEY = os.environ.get("API_KEY")

# Create trigger for notification
def send_maintenance_notification(payload):
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI'] #best
    try: #handle issues
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs: #using cursor() wrapper on try catch.
             curs.execute(f"NOTIFY maintenance_updates, %s;", (json.dumps(payload),)) #trigger notification here.
        conn.close() #close connection

    except psycopg2.Error as e:
        print(f"Error on sending : {e}")# error message


def send_maintenance_logs_notification(payload):
    """Sends a notification for maintenance activity log updates."""
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    try:
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:
            curs.execute(f"NOTIFY maintenance_logs_updates, %s;", (json.dumps(payload),))
        conn.close()
    except psycopg2.Error as e:
        print(f"Error sending maintenance activity log notification: {e}")



@maintenance_api.get("/maintenance")
def maintenance_data():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

        query_data = Maintenance.query.all()

        if not query_data:
            return jsonify(message="No maintenance data found."), 404

        maintenance_dict = [{
            "maintenance_id": data.maintenance_id,
            "email": data.users.email,
            "title": data.title,
            "name": data.name,
            "date_completed": data.date_completed.strftime("%Y-%m-%d %H:%M:%S") if data.date_completed else None,
            "description": data.description,
        } for data in query_data]

        return jsonify(maintenance_dict), 200

    except Exception as e:
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@maintenance_api.post("/maintenance")
def add_maintenance():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Incorrect api_key."}
            ), 403

        title = request.form.get("title")
        description = request.form.get("description")
        email = request.form.get("email")
        name = request.form.get("name")

        # Validate required fields
        if not all([title, description, email, name]):
            return jsonify(error={"message": "All fields are required"}), 400

        # Check if user exists
        user = Users.query.filter_by(email=email).first()
        if not user:
            return jsonify(error={"message": f"User with email {email} not found"}), 404

        new_maintenance = Maintenance(
            user_id=user.user_id,
            title=title,
            description=description,
            name=name,
            date_completed=datetime.utcnow()  # Remove or keep
        )

        db.session.add(new_maintenance)
        db.session.commit()  # Commit to generate maintenance_id

        # Create activity log before.,. and,. best put here, during, commit db first: so will, make track first,. harvest : then next logs., it can
        # and catch this.,, harvest logs,.,
        ph_tz = pytz.timezone('Asia/Manila')
        manila_now = datetime.now(ph_tz).replace(tzinfo=None)
        new_log = MaintenanceActivityLogs(
            login_id=user.user_id,
            maintenance_id=new_maintenance.maintenance_id,
            logs_description="New Maintenance added",
            log_date=manila_now,
            name=name
        )
        db.session.add(new_log)
        db.session.commit()# and commit

        # Trigger notification
        send_maintenance_notification({  # sent notifiy
             "action": "insert",
             "maintenance_id": new_maintenance.maintenance_id
         })

         # Trigger Logs Changes
        send_maintenance_logs_notification({#Sent trigger maintenance, via notify ,., with., postgress changes notifica
              "action": "insert",
               "log_id":new_log.log_id
        })# logs/  sent , if
        return jsonify(
            message="Maintenance added successfully",
            maintenance_id=new_maintenance.maintenance_id
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"Error: {str(e)}"}), 500



@maintenance_api.delete("/maintenance")
def delete_all_maintenance():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Incorrect api_key."}
            ), 403

        # FIRST: Delete all related MaintenanceActivityLogs
        maintenance_ids = [m.maintenance_id for m in Maintenance.query.all()] #collects all id

        MaintenanceActivityLogs.query.delete() #delete logs activity
        # THEN: Delete all Maintenance records
        num_maintenance_deleted = Maintenance.query.delete()

        db.session.commit() #commit , first befor

        for maintenance_id in maintenance_ids:#loops of, `all deleted ids` before deletion ,
            send_maintenance_notification({# Sent the event : trigger to delete
                "action": "delete", # Sent the information  via Action details : and id of the
                "maintenance_id": maintenance_id #trigger by maintanenance models if deleted , then it sent.
            })#loops of  deleted id records ,  before deleting and `to make and Sent action/details that trigger  notification: to. : by ID  logs ,`. maintenance id,. all
        #for logs Id all, deleted: to : to: and make, notications: delete: event socket,.. , send information to server Flask: for via this,..

        return jsonify(
            message=f"Deleted {num_maintenance_deleted} maintenance records and associated logs."
        ), 200

    except Exception as e:
        db.session.rollback() #Rollback , make and changes undo during unsuccessfull operation of delete
        return jsonify(error={"message": str(e)}), 500  #Error logs

# C:\Users\Giebert\PycharmProjects\agreemo_api\routes\hardware_status_routes.py
import datetime
import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, current_app  # Import current_app
from datetime import datetime
from db import db
import pytz
from functions import log_activity
from models import HardwareCurrentStatus, Greenhouse, HardwareComponents
from models.activity_logs.hardware_status_logs_model import HardwareStatusActivityLogs
import psycopg2  # Import
import json  # Import

hardware_status_api = Blueprint("hardware_status_api", __name__)

API_KEY = os.environ.get("API_KEY")


# --Trigger new method, update changes to database
def send_hardware_status_notification(payload): #add
    db_uri = current_app.config['SQLALCHEMY_DATABASE_URI'] # get db uri
    try:#Error Checking best
        conn = psycopg2.connect(db_uri)
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as curs:  # curs wrapper to the try catch block.
            curs.execute(f"NOTIFY hardware_status_updates, %s;", (json.dumps(payload),))# Trigger notifications.
        conn.close() # Close connect.
    except psycopg2.Error as e:#If Error exception handle.
        print(f"Failed and Issue :  {e}") #print the logs.

@hardware_status_api.get("/hardware_status")
def hardware_status_data():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403

        query_data = HardwareCurrentStatus.query.all()

        if not query_data:
            return jsonify(message="No hardware status data found."), 404

        hardware_status_dict = [{
            "component_id": data.component_id,
            "isActive": data.isActive,
            "greenhouse_id": data.greenhouse_id,
            "lastChecked": data.lastChecked,
            "statusNote": data.statusNote,
        } for data in query_data]

        return jsonify(hardware_status_dict), 200

    except Exception as e:
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


# add for developer use only
def parse_timestamp(ts):
    """
    Parse the timestamp (which might be a string) into a UTC-aware datetime.
    Expected string format: "Sun, 16 Feb 2025 10:12:25 GMT"
    """
    if isinstance(ts, str):
        dt_naive = datetime.strptime(ts, "%a, %d %b %Y %H:%M:%S %Z")
        # The parsed datetime is naive; set it to UTC.
        return dt_naive.replace(tzinfo=timezone.utc)
    else:
        # Assume it's already a datetime.
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts


@hardware_status_api.post("/hardware_status/add")
def hardware_status_add():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Sorry, that's not allowed. Make sure you have the correct api_key."}
            ), 403

        greenhouse_id = request.form.get("greenhouse_id")
        greenhouse = Greenhouse.query.get(greenhouse_id)
        if not greenhouse:
            return jsonify(error={"message": "Greenhouse not found!"}), 404

        component_id = request.form.get("component_id")
        component = HardwareComponents.query.get(component_id)
        if not component:
            return jsonify(error={"message": "Hardware Components not found!"}), 404

        isActive = request.form.get("isActive")
        isActive = True if isActive == '1' else False  # Convert string '1' to True, else False
        statusNote = request.form.get("statusNote")

        ph_tz = pytz.timezone('Asia/Manila')
        manila_now = datetime.now(ph_tz)
        naive_manila_now = manila_now.replace(tzinfo=None)  # Convert to naive datetime

        # Fetch the most recent log for the same component and greenhouse.
        last_record = HardwareStatusActivityLogs.query.filter_by(
            component_id=component_id, greenhouse_id=greenhouse_id
        ).order_by(HardwareStatusActivityLogs.timestamp.desc()).first()

        # Determine duration:
        if isActive:
            duration = "0"
        else:
            if last_record:
                if last_record.status is True:  # Transition from active to inactive
                    last_active_time = parse_timestamp(last_record.timestamp)
                    time_diff = naive_manila_now - last_active_time
                    duration = format_duration(time_diff)
                else:  # Previous record already inactive
                    duration = "N/A"
            else:
                duration = "N/A"



        new_hardware_status = HardwareCurrentStatus(
            component_id=component_id,
            greenhouse_id=greenhouse_id,
            isActive=isActive,
            statusNote=statusNote,
            lastChecked=naive_manila_now,
        )
        db.session.add(new_hardware_status)



        new_hardware_status_activity_logs = HardwareStatusActivityLogs(
            greenhouse_id=greenhouse_id,
            component_id=component_id,
            logs_description= f"New Hardware Current Status successfully added!",
            duration=duration,
            status=isActive,
            timestamp=naive_manila_now,
        )
        db.session.add(new_hardware_status_activity_logs)

        db.session.commit()#commit chanes


        send_hardware_status_notification({#sends new hardware trigger notifications.
             "action":"insert",# set and Pass Action
             "component_id": component_id# component id new updates.
         })

        return jsonify(message="Hardware Current Status successfully added!"), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"Message": f"Failed to add. Error: {str(e)}"}), 500




def format_duration(time_diff):
    """
    Convert a timedelta object into a human-readable format:
    """
    total_seconds = int(time_diff.total_seconds())

    months = (total_seconds % (365 * 24 * 3600)) // (30 * 24 * 3600)
    days = (total_seconds % (30 * 24 * 3600)) // (24 * 3600)
    years = total_seconds // (365 * 24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    duration_parts = []
    if years > 0:
        duration_parts.append(f"{years} year{'s' if years > 1 else ''}")
    if months > 0:
        duration_parts.append(f"{months} month{'s' if months > 1 else ''}")
    if days > 0:
        duration_parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        duration_parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        duration_parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0 or not duration_parts:
        duration_parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return " and ".join(duration_parts)

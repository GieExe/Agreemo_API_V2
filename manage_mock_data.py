import sys
import os
from datetime import datetime, timedelta
import pytz
import random

# Add project root to Python path to allow importing models
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- MODIFIED APP/DB IMPORT AND CONTEXT SETUP ---
try:
    # Import the existing 'app' instance created in app.py
    from app import app
    # Import the 'db' instance created in db.py (assuming db.py has db = SQLAlchemy())
    from db import db

    # Manually create and push an application context
    # This makes 'current_app' available and sets up the DB session context
    app_context = app.app_context()
    app_context.push()

    print("Flask app context created successfully using imported 'app' instance.")

    # Optional verification: Check if db has been initialized by app.py
    if not hasattr(db, 'session'):
         print("Warning: 'db' object imported but Flask-SQLAlchemy session might not be active.")
         # If db.init_app(app) was definitely called in app.py, this warning is likely unnecessary

except ImportError as e:
    # This block will run if 'app.py' or 'db.py' cannot be found/imported
    db = None
    app = None
    app_context = None
    print(f"Warning: Could not import 'app' or 'db'. Running without app context. Error: {e}")
    print("Database operations will likely fail unless DB is configured independently.")
# --- END OF MODIFIED BLOCK ---

# Import Models (ensure paths are correct)
from models.inventory_model import Inventory, InventoryContainer
from models.activity_logs.inventory_log_model import InventoryLog
from models.activity_logs.inventory_container_activity_logs import InventoryContainerLog
from models.sensors_readings_model import SensorReading
from models.nutrient_controllers_model import NutrientController
from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs
from models.users_model import Users # Needed for user lookup/ID

# --- Configuration ---
PH_TZ = pytz.timezone('Asia/Manila')
TARGET_PLANT_ID = 600
TARGET_PLANT_NAME = "P600-031725"
TARGET_GREENHOUSE_ID = 8
SETUP_USER_EMAIL = "boszcris70@gmail.com"
# Assume User ID 20 for boszcris70@gmail.com (fetch or hardcode)
SETUP_USER_ID = 20
# Assume User ID NULL or a system user ID for automatic actions
# Check if your InventoryContainerLog model allows NULL for user_id
AUTO_ACTION_USER_ID = None # Use None for NULL (ensure DB/Model allows it)

# Starting IDs (increment these in a real generation loop)
start_ids = {
    "inventory": 601,
    "inventory_log": 1001,
    "inventory_container": 9, # Assuming 9 is next or the one for GH 8
    "inventory_container_log": 2001,
    "sensor_reading": 5001,
    "nutrient_controller": 301,
    "nutrient_controller_log": 401,
}

# Lists to store generated IDs for reverting
generated_ids = {
    "inventory": [],
    "inventory_log": [],
    "inventory_container_log": [],
    "sensor_reading": [],
    "nutrient_controller": [],
    "nutrient_controller_log": [],
}

# --- Helper Functions ---
def format_datetime_for_db(dt_obj):
    """ Formats datetime to string suitable for DB insertion if needed,
        or returns the object if the ORM handles it. """
    if isinstance(dt_obj, datetime):
         return dt_obj # Let SQLAlchemy handle timezone-aware types if configured
    return dt_obj

def get_next_id(key):
    """Gets the next ID and increments the counter."""
    current_id = start_ids[key]
    start_ids[key] += 1
    return current_id

# --- Mock Data Generation (Representative Sample) ---

# Phase 1: Initial Setup Data (Manual Action)
mock_inventory = [
    {"inventory_id": 601, "greenhouse_id": 8, "item_name": "pH Up Solution (1L)", "user_name": "Cris B.", "type": "ph_up", "quantity": 1, "total_price": 150.00, "max_total_ml": 1000.0, "created_at": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 1)), "price": 150.00},
    {"inventory_id": 602, "greenhouse_id": 8, "item_name": "pH Down Solution (1L)", "user_name": "Cris B.", "type": "ph_down", "quantity": 1, "total_price": 140.00, "max_total_ml": 1000.0, "created_at": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 2)), "price": 140.00},
    {"inventory_id": 603, "greenhouse_id": 8, "item_name": "HydroGrow Nutrient A (1L)", "user_name": "Cris B.", "type": "solution_a", "quantity": 1, "total_price": 250.00, "max_total_ml": 1000.0, "created_at": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 3)), "price": 250.00},
    {"inventory_id": 604, "greenhouse_id": 8, "item_name": "HydroGrow Nutrient B (1L)", "user_name": "Cris B.", "type": "solution_b", "quantity": 1, "total_price": 250.00, "max_total_ml": 1000.0, "created_at": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 4)), "price": 250.00},
]
mock_inventory_logs = [
    {"log_id": 1001, "inventory_id": 601, "user_id": SETUP_USER_ID, "change_type": "create", "description": "Created inventory item 'pH Up Solution (1L)' (Type: ph_up), Qty: 1, Price: 150.0, Max ML: 1000.0 by user boszcris70@gmail.com.", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 1))},
    {"log_id": 1002, "inventory_id": 602, "user_id": SETUP_USER_ID, "change_type": "create", "description": "Created inventory item 'pH Down Solution (1L)' (Type: ph_down), Qty: 1, Price: 140.0, Max ML: 1000.0 by user boszcris70@gmail.com.", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 2))},
    {"log_id": 1003, "inventory_id": 603, "user_id": SETUP_USER_ID, "change_type": "create", "description": "Created inventory item 'HydroGrow Nutrient A (1L)' (Type: solution_a), Qty: 1, Price: 250.0, Max ML: 1000.0 by user boszcris70@gmail.com.", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 3))},
    {"log_id": 1004, "inventory_id": 604, "user_id": SETUP_USER_ID, "change_type": "create", "description": "Created inventory item 'HydroGrow Nutrient B (1L)' (Type: solution_b), Qty: 1, Price: 250.0, Max ML: 1000.0 by user boszcris70@gmail.com.", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 4))},
]
# We need logs reflecting the container fields being set AND the change_type
mock_inventory_container_logs_phase1 = [
    {"log_id": 2001, "inventory_container_id": 9, "user_id": SETUP_USER_ID, "item": "ph_up", "old_quantity": 0.0, "new_quantity": 1000.0, "change_type": "create", "description": "Created container and set field 'ph_up' via creation of inventory item 'pH Up Solution (1L)' (ID: 601)", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 1))}, # Assuming this log comes from the *creation* call
    {"log_id": 2002, "inventory_container_id": 9, "user_id": SETUP_USER_ID, "item": "ph_down", "old_quantity": 0.0, "new_quantity": 1000.0, "change_type": "update", "description": "Container field 'ph_down' updated via creation of inventory item 'pH Down Solution (1L)' (ID: 602)", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 2))}, # Subsequent ones are updates
    {"log_id": 2003, "inventory_container_id": 9, "user_id": SETUP_USER_ID, "item": "solution_a", "old_quantity": 0.0, "new_quantity": 1000.0, "change_type": "update", "description": "Container field 'solution_a' updated via creation of inventory item 'HydroGrow Nutrient A (1L)' (ID: 603)", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 3))},
    {"log_id": 2004, "inventory_container_id": 9, "user_id": SETUP_USER_ID, "item": "solution_b", "old_quantity": 0.0, "new_quantity": 1000.0, "change_type": "update", "description": "Container field 'solution_b' updated via creation of inventory item 'HydroGrow Nutrient B (1L)' (ID: 604)", "timestamp": PH_TZ.localize(datetime(2025, 3, 17, 9, 0, 4))},
]


# Phase 2: Automated Readings & Adjustments (Sample Data)
# Initial state for simulation (after phase 1)
container_levels = {"ph_up": 1000.0, "ph_down": 1000.0, "solution_a": 1000.0, "solution_b": 1000.0}
current_ph = 6.2
current_tds = 640.0

mock_sensor_readings = []
mock_nutrient_controllers = []
mock_nutrient_controller_logs = []
mock_inventory_container_logs_phase2 = []

# --- Sample: March 17, 14:00 ---
reading_time_1 = PH_TZ.localize(datetime(2025, 3, 17, 14, 0, 0))
current_ph = 6.6 # Too high
current_tds = 630.0 # Too low (Target ~650)
mock_sensor_readings.extend([
    {"reading_id": 5005, "reading_value": current_ph, "reading_time": reading_time_1, "unit": "pH"},
    {"reading_id": 5006, "reading_value": current_tds, "reading_time": reading_time_1 + timedelta(seconds=5), "unit": "ppm"},
])
# Adjust pH Down
dispensed_ph_down = 5.0
controller_id_phd = 301
nc_log_id_phd = 401
inv_cont_log_id_phd = 2005
old_level = container_levels["ph_down"]
container_levels["ph_down"] -= dispensed_ph_down
mock_nutrient_controllers.append(
    {"controller_id": controller_id_phd, "greenhouse_id": 8, "plant_id": 600, "plant_name": TARGET_PLANT_NAME, "solution_type": "pH Down", "dispensed_amount": dispensed_ph_down, "activated_by": "Auto", "dispensed_time": reading_time_1 + timedelta(minutes=1)}
)
mock_nutrient_controller_logs.append(
    {"log_id": nc_log_id_phd, "controller_id": controller_id_phd, "greenhouse_id": 8, "activated_by": "Auto", "logs_description": f"Nutrient dose of {dispensed_ph_down}ml pH Down applied to plant '{TARGET_PLANT_NAME}' (ID: 600). Triggered by pH reading: {current_ph:.1f}", "logs_date": reading_time_1 + timedelta(minutes=1)}
)
mock_inventory_container_logs_phase2.append(
     {"log_id": inv_cont_log_id_phd, "inventory_container_id": 9, "user_id": AUTO_ACTION_USER_ID, "item": "ph_down", "old_quantity": old_level, "new_quantity": container_levels["ph_down"], "change_type": "remove", "description": f"Dispensed {dispensed_ph_down} ml of pH Down for plant '{TARGET_PLANT_NAME}' (ID: 600). | Trigger: Auto", "timestamp": reading_time_1 + timedelta(minutes=1)}
)
current_ph = 6.1

# Adjust Nutrients A & B
dispensed_nutes = 15.0
controller_id_na = 302
controller_id_nb = 303
nc_log_id_na = 402
nc_log_id_nb = 403
inv_cont_log_id_na = 2006
inv_cont_log_id_nb = 2007
old_level_a = container_levels["solution_a"]
old_level_b = container_levels["solution_b"]
container_levels["solution_a"] -= dispensed_nutes
container_levels["solution_b"] -= dispensed_nutes
mock_nutrient_controllers.extend([
    {"controller_id": controller_id_na, "greenhouse_id": 8, "plant_id": 600, "plant_name": TARGET_PLANT_NAME, "solution_type": "Nutrient A", "dispensed_amount": dispensed_nutes, "activated_by": "Auto", "dispensed_time": reading_time_1 + timedelta(minutes=2)},
    {"controller_id": controller_id_nb, "greenhouse_id": 8, "plant_id": 600, "plant_name": TARGET_PLANT_NAME, "solution_type": "Nutrient B", "dispensed_amount": dispensed_nutes, "activated_by": "Auto", "dispensed_time": reading_time_1 + timedelta(minutes=2, seconds=5)}
])
mock_nutrient_controller_logs.extend([
    {"log_id": nc_log_id_na, "controller_id": controller_id_na, "greenhouse_id": 8, "activated_by": "Auto", "logs_description": f"Nutrient dose of {dispensed_nutes}ml Nutrient A applied to plant '{TARGET_PLANT_NAME}' (ID: 600). Triggered by TDS reading: {current_tds:.1f}", "logs_date": reading_time_1 + timedelta(minutes=2)},
    {"log_id": nc_log_id_nb, "controller_id": controller_id_nb, "greenhouse_id": 8, "activated_by": "Auto", "logs_description": f"Nutrient dose of {dispensed_nutes}ml Nutrient B applied to plant '{TARGET_PLANT_NAME}' (ID: 600). Triggered by TDS reading: {current_tds:.1f}", "logs_date": reading_time_1 + timedelta(minutes=2, seconds=5)}
])
mock_inventory_container_logs_phase2.extend([
     {"log_id": inv_cont_log_id_na, "inventory_container_id": 9, "user_id": AUTO_ACTION_USER_ID, "item": "solution_a", "old_quantity": old_level_a, "new_quantity": container_levels["solution_a"], "change_type": "remove", "description": f"Dispensed {dispensed_nutes} ml of Nutrient A for plant '{TARGET_PLANT_NAME}' (ID: 600). | Trigger: Auto", "timestamp": reading_time_1 + timedelta(minutes=2)},
     {"log_id": inv_cont_log_id_nb, "inventory_container_id": 9, "user_id": AUTO_ACTION_USER_ID, "item": "solution_b", "old_quantity": old_level_b, "new_quantity": container_levels["solution_b"], "change_type": "remove", "description": f"Dispensed {dispensed_nutes} ml of Nutrient B for plant '{TARGET_PLANT_NAME}' (ID: 600). | Trigger: Auto", "timestamp": reading_time_1 + timedelta(minutes=2, seconds=5)}
])
current_tds = 680.0

# --- Sample: April 10, 10:00 ---
reading_time_2 = PH_TZ.localize(datetime(2025, 4, 10, 10, 0, 0))
current_ph = 5.4 # Too low
current_tds = 780.0 # Slightly low (Target ~800)
mock_sensor_readings.extend([
    {"reading_id": 5201, "reading_value": current_ph, "reading_time": reading_time_2, "unit": "pH"},
    {"reading_id": 5202, "reading_value": current_tds, "reading_time": reading_time_2 + timedelta(seconds=5), "unit": "ppm"},
])
# Adjust pH Up
dispensed_ph_up = 8.0
controller_id_phu = 350
nc_log_id_phu = 450
inv_cont_log_id_phu = 2050
old_level = container_levels["ph_up"]
container_levels["ph_up"] -= dispensed_ph_up
mock_nutrient_controllers.append(
    {"controller_id": controller_id_phu, "greenhouse_id": 8, "plant_id": 600, "plant_name": TARGET_PLANT_NAME, "solution_type": "pH Up", "dispensed_amount": dispensed_ph_up, "activated_by": "Auto", "dispensed_time": reading_time_2 + timedelta(minutes=1)}
)
mock_nutrient_controller_logs.append(
    {"log_id": nc_log_id_phu, "controller_id": controller_id_phu, "greenhouse_id": 8, "activated_by": "Auto", "logs_description": f"Nutrient dose of {dispensed_ph_up}ml pH Up applied to plant '{TARGET_PLANT_NAME}' (ID: 600). Triggered by pH reading: {current_ph:.1f}", "logs_date": reading_time_2 + timedelta(minutes=1)}
)
mock_inventory_container_logs_phase2.append(
     {"log_id": inv_cont_log_id_phu, "inventory_container_id": 9, "user_id": AUTO_ACTION_USER_ID, "item": "ph_up", "old_quantity": old_level, "new_quantity": container_levels["ph_up"], "change_type": "remove", "description": f"Dispensed {dispensed_ph_up} ml of pH Up for plant '{TARGET_PLANT_NAME}' (ID: 600). | Trigger: Auto", "timestamp": reading_time_2 + timedelta(minutes=1)}
)
current_ph = 5.9

# Adjust Nutrients A & B
dispensed_nutes_2 = 20.0
controller_id_na2 = 351
controller_id_nb2 = 352
nc_log_id_na2 = 451
nc_log_id_nb2 = 452
inv_cont_log_id_na2 = 2051
inv_cont_log_id_nb2 = 2052
old_level_a = container_levels["solution_a"]
old_level_b = container_levels["solution_b"]
container_levels["solution_a"] -= dispensed_nutes_2
container_levels["solution_b"] -= dispensed_nutes_2
mock_nutrient_controllers.extend([
    {"controller_id": controller_id_na2, "greenhouse_id": 8, "plant_id": 600, "plant_name": TARGET_PLANT_NAME, "solution_type": "Nutrient A", "dispensed_amount": dispensed_nutes_2, "activated_by": "Auto", "dispensed_time": reading_time_2 + timedelta(minutes=2)},
    {"controller_id": controller_id_nb2, "greenhouse_id": 8, "plant_id": 600, "plant_name": TARGET_PLANT_NAME, "solution_type": "Nutrient B", "dispensed_amount": dispensed_nutes_2, "activated_by": "Auto", "dispensed_time": reading_time_2 + timedelta(minutes=2, seconds=5)}
])
mock_nutrient_controller_logs.extend([
    {"log_id": nc_log_id_na2, "controller_id": controller_id_na2, "greenhouse_id": 8, "activated_by": "Auto", "logs_description": f"Nutrient dose of {dispensed_nutes_2}ml Nutrient A applied to plant '{TARGET_PLANT_NAME}' (ID: 600). Triggered by TDS reading: {current_tds:.1f}", "logs_date": reading_time_2 + timedelta(minutes=2)},
    {"log_id": nc_log_id_nb2, "controller_id": controller_id_nb2, "greenhouse_id": 8, "activated_by": "Auto", "logs_description": f"Nutrient dose of {dispensed_nutes_2}ml Nutrient B applied to plant '{TARGET_PLANT_NAME}' (ID: 600). Triggered by TDS reading: {current_tds:.1f}", "logs_date": reading_time_2 + timedelta(minutes=2, seconds=5)}
])
mock_inventory_container_logs_phase2.extend([
     {"log_id": inv_cont_log_id_na2, "inventory_container_id": 9, "user_id": AUTO_ACTION_USER_ID, "item": "solution_a", "old_quantity": old_level_a, "new_quantity": container_levels["solution_a"], "change_type": "remove", "description": f"Dispensed {dispensed_nutes_2} ml of Nutrient A for plant '{TARGET_PLANT_NAME}' (ID: 600). | Trigger: Auto", "timestamp": reading_time_2 + timedelta(minutes=2)},
     {"log_id": inv_cont_log_id_nb2, "inventory_container_id": 9, "user_id": AUTO_ACTION_USER_ID, "item": "solution_b", "old_quantity": old_level_b, "new_quantity": container_levels["solution_b"], "change_type": "remove", "description": f"Dispensed {dispensed_nutes_2} ml of Nutrient B for plant '{TARGET_PLANT_NAME}' (ID: 600). | Trigger: Auto", "timestamp": reading_time_2 + timedelta(minutes=2, seconds=5)}
])
current_tds = 830.0

# --- Final Container State (After Sample Adjustments) ---
print(f"\nContainer Levels after sample adjustments: {container_levels}\n")

# Combine container logs
all_mock_inventory_container_logs = mock_inventory_container_logs_phase1 + mock_inventory_container_logs_phase2

# --- Insertion Function ---
def insert_mock_data():
    """Inserts the generated mock data into the database."""
    # *** Check if app and db were initialized ***
    if not db or not app:
        print("Error: DB or Flask app not initialized. Cannot insert data.")
        return

    # *** Ensure operations run within the app context pushed earlier ***
    # No need for 'with app_context:' here if it was pushed globally at the start
    print("Starting mock data insertion...")
    try:
        # 1. Insert Inventory Items
        for item_data in mock_inventory:
            # Convert datetime to compatible format if necessary, else let ORM handle
            item_data['created_at'] = format_datetime_for_db(item_data['created_at'])
            item = Inventory(**item_data)
            db.session.add(item)
            # Flush to get ID before adding to list might be safer if FK relies on it
            db.session.flush()
            generated_ids["inventory"].append(item.inventory_id)
        print(f"Added {len(mock_inventory)} Inventory items.")

        # 2. Insert Inventory Logs
        for log_data in mock_inventory_logs:
            log_data['timestamp'] = format_datetime_for_db(log_data['timestamp'])
            log = InventoryLog(**log_data)
            db.session.add(log)
            db.session.flush()
            generated_ids["inventory_log"].append(log.log_id)
        print(f"Added {len(mock_inventory_logs)} InventoryLog entries.")

        # 3. Update Inventory Container (Assume container 9 exists for GH 8)
        # This script now assumes the container is managed by the main app routes
        # It only inserts the LOGS for the container changes
        container = db.session.get(InventoryContainer, start_ids["inventory_container"])
        if not container:
             print(f"Warning: InventoryContainer ID {start_ids['inventory_container']} for GH {TARGET_GREENHOUSE_ID} not found. Container logs might fail or link incorrectly.")
             # For a standalone script, you might need logic here to create/update
             # the container based on the initial inventory mock data.

        # 4. Insert Inventory Container Logs (Phase 1 & 2)
        for log_data in all_mock_inventory_container_logs:
             log_data['timestamp'] = format_datetime_for_db(log_data['timestamp'])
             # Handle potential None user_id based on model allowance
             log_user_id = log_data.get("user_id")
             log_data_db = {k: v for k, v in log_data.items() if k != 'user_id'} # Prepare dict
             log_data_db['user_id'] = log_user_id # Add user_id back (could be None)

             log = InventoryContainerLog(**log_data_db)
             db.session.add(log)
             db.session.flush()
             generated_ids["inventory_container_log"].append(log.log_id)
        print(f"Added {len(all_mock_inventory_container_logs)} InventoryContainerLog entries.")

        # 5. Insert Sensor Readings
        for reading_data in mock_sensor_readings:
            reading_data['reading_time'] = format_datetime_for_db(reading_data['reading_time'])
            reading = SensorReading(**reading_data)
            db.session.add(reading)
            db.session.flush()
            generated_ids["sensor_reading"].append(reading.reading_id)
        print(f"Added {len(mock_sensor_readings)} SensorReading entries.")

        # 6. Insert Nutrient Controller Events
        for nc_data in mock_nutrient_controllers:
            nc_data['dispensed_time'] = format_datetime_for_db(nc_data['dispensed_time'])
            nc = NutrientController(**nc_data)
            db.session.add(nc)
            db.session.flush()
            generated_ids["nutrient_controller"].append(nc.controller_id)
        print(f"Added {len(mock_nutrient_controllers)} NutrientController entries.")

        # 7. Insert Nutrient Controller Logs
        for log_data in mock_nutrient_controller_logs:
            log_data['logs_date'] = format_datetime_for_db(log_data['logs_date'])
            log = NutrientControllerActivityLogs(**log_data)
            db.session.add(log)
            db.session.flush()
            generated_ids["nutrient_controller_log"].append(log.log_id)
        print(f"Added {len(mock_nutrient_controller_logs)} NutrientControllerActivityLogs entries.")

        # Commit all changes at the end
        db.session.commit()
        print("Mock data insertion committed successfully.")
        print("Generated IDs:", generated_ids)

    except Exception as e:
        db.session.rollback() # Rollback on any error
        print(f"Error during insertion: {e}")
        import traceback
        traceback.print_exc()
    finally:
         print("Insertion process finished.")


# --- Reversion Function ---
def revert_mock_data():
    """Deletes the mock data inserted by this script."""
    # *** Check if app and db were initialized ***
    if not db or not app:
        print("Error: DB or Flask app not initialized. Cannot revert data.")
        return

    # *** Ensure operations run within the app context pushed earlier ***
    print("Starting mock data reversion...")
    try:
        # Delete in an order that respects potential FK constraints
        # Logs often depend on main records, delete logs first

        if generated_ids["nutrient_controller_log"]:
            print(f"Deleting {len(generated_ids['nutrient_controller_log'])} NutrientControllerActivityLogs entries...")
            db.session.query(NutrientControllerActivityLogs).filter(NutrientControllerActivityLogs.log_id.in_(generated_ids["nutrient_controller_log"])).delete(synchronize_session=False)

        if generated_ids["nutrient_controller"]:
            print(f"Deleting {len(generated_ids['nutrient_controller'])} NutrientController entries...")
            db.session.query(NutrientController).filter(NutrientController.controller_id.in_(generated_ids["nutrient_controller"])).delete(synchronize_session=False)

        if generated_ids["sensor_reading"]:
            print(f"Deleting {len(generated_ids['sensor_reading'])} SensorReading entries...")
            db.session.query(SensorReading).filter(SensorReading.reading_id.in_(generated_ids["sensor_reading"])).delete(synchronize_session=False)

        if generated_ids["inventory_container_log"]:
             print(f"Deleting {len(generated_ids['inventory_container_log'])} InventoryContainerLog entries...")
             db.session.query(InventoryContainerLog).filter(InventoryContainerLog.log_id.in_(generated_ids["inventory_container_log"])).delete(synchronize_session=False)

        if generated_ids["inventory_log"]:
             print(f"Deleting {len(generated_ids['inventory_log'])} InventoryLog entries...")
             db.session.query(InventoryLog).filter(InventoryLog.log_id.in_(generated_ids["inventory_log"])).delete(synchronize_session=False)

        # Delete Inventory Items last as other things might reference them
        if generated_ids["inventory"]:
            print(f"Deleting {len(generated_ids['inventory'])} Inventory entries...")
            # Add check: Ensure InventoryContainer isn't pointing to these IDs first if necessary
            # containers_referencing = db.session.query(InventoryContainer).filter(InventoryContainer.inventory_id.in_(generated_ids["inventory"])).count()
            # if containers_referencing > 0:
            #    print(f"Warning: Cannot delete Inventory items because {containers_referencing} InventoryContainer(s) still reference them.")
            # else:
            #    db.session.query(Inventory).filter(Inventory.inventory_id.in_(generated_ids["inventory"])).delete(synchronize_session=False)
            # Safer: Just attempt deletion and let DB handle FK constraint errors if any exist
            db.session.query(Inventory).filter(Inventory.inventory_id.in_(generated_ids["inventory"])).delete(synchronize_session=False)


        db.session.commit()
        print("Mock data reversion committed successfully.")
        # Clear generated IDs after successful revert
        for key in generated_ids:
            generated_ids[key] = []
        print("Cleared generated ID list.")

    except Exception as e:
        db.session.rollback()
        print(f"Error during reversion: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Reversion process finished.")

# --- Main Execution ---
if __name__ == "__main__":
    # Simple command-line argument handling
    action = input("Enter action (insert / revert): ").strip().lower()

    if action == "insert":
        insert_mock_data()
    elif action == "revert":
        # Optional: Load IDs if saved previously, otherwise relies on in-memory list
        if not any(v for v in generated_ids.values() if v): # Check if any list has content
             print("No generated IDs found in memory from this session. Cannot revert.")
             print("You might need to manually identify and delete records.")
        else:
            print("Reverting data with the following IDs tracked in this session:")
            for key, id_list in generated_ids.items():
                 if id_list:
                     print(f"  {key}: {id_list}")
            confirm = input("Are you sure you want to delete these records? (yes/no): ").strip().lower()
            if confirm == "yes":
                revert_mock_data()
            else:
                print("Reversion cancelled.")
    else:
        print("Invalid action. Please use 'insert' or 'revert'.")

    # Pop Flask app context if it was pushed AND successfully created
    if app_context:
        try:
            app_context.pop()
            print("Flask app context popped.")
        except Exception as pop_e:
            # Context might have already been popped or was never pushed properly
            print(f"Info: Issue popping Flask app context (may be expected): {pop_e}")
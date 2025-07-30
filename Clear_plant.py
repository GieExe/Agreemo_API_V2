# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\Clear_plant.py


import sys
import os
import argparse
import traceback
from sqlalchemy import text # For raw SQL

# --- Project Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Flask App and DB ---
try:
    from app import app
    from db import db
except ImportError as e:
    print(f"Error importing Flask app or db instance: {e}")
    sys.exit(1)

# --- Model Imports ---
# Include all relevant models, even if using raw SQL, for context and potential future use.
try:
    # Plant Related
    from models.planted_crops_model import PlantedCrops
    from models.activity_logs.planted_crop_activity_logs_model import PlantedCropActivityLogs
    # Nutrient Controller Related
    from models.nutrient_controllers_model import NutrientController
    from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs
    # Harvest Related (Already present in original example)
    from models.harvest_model import Harvest
    from models.activity_logs.harvest_activity_logs_model import HarvestActivityLogs
    # Sale Related (Already present in original example)
    from models.sale_model import Sale
    from models.activity_logs.sale_activity_log_model import SaleLog # Assuming this exists based on original example
except ImportError as e:
    # Log the error but proceed, as raw SQL doesn't strictly need the ORM models here
    print(f"Warning: Could not import some models: {e}. Proceeding with raw SQL.")
    # Define as None to avoid NameError if used elsewhere accidentally
    PlantedCrops = None
    PlantedCropActivityLogs = None
    NutrientController = None
    NutrientControllerActivityLogs = None
    Harvest = None
    HarvestActivityLogs = None
    Sale = None
    SaleLog = None

# --- Data Cleanup Function for Plant, Nutrient, Harvest & Sales Data using Raw SQL ---
def clear_plant_related_data_raw_sql():
    """
    Deletes ALL data from relevant tables:
    - sale_logs
    - sales
    - harvest_activity_logs
    - nutrient_controller_activity_logs
    - planted_crop_activity_logs
    - harvests
    - nutrient_controllers
    - planted_crops
    using RAW SQL. This bypasses SQLAlchemy ORM relationship checks but respects
    database-level Foreign Key constraints. Use with extreme caution!
    Deletion order is critical due to FKs.
    """
    print(f"--- Starting Plant, Nutrient, Harvest & Sales Data Cleanup (using Raw SQL) ---")
    print("    WARNING: This will delete ALL data from:")
    print("      - sale_logs, sales")
    print("      - harvest_activity_logs, harvests")
    print("      - nutrient_controller_activity_logs, nutrient_controllers")
    print("      - planted_crop_activity_logs, planted_crops")

    # Safety confirmation prompt - Updated to be more specific
    confirm = input("    Type 'DELETE ALL PLANT NUTRIENT HARVEST SALES DATA RAW' exactly to confirm: ")
    if confirm != "DELETE ALL PLANT NUTRIENT HARVEST SALES DATA RAW":
        print("    Cleanup aborted by user.")
        return False # Indicate abortion

    try:
        print("\n[Deletion] Starting deletion process (raw SQL, respecting FKs)...")

        # --- Execute RAW SQL DELETE statements in dependency order ---
        # Order: Delete logs first, then dependent tables, then the core tables.

        # 1. Delete Sale Logs (depends on Sales)
        sql_delete_sale_logs = text("DELETE FROM sale_logs;")
        print(f"  - Executing: {sql_delete_sale_logs}")
        result_sale_logs = db.session.execute(sql_delete_sale_logs)
        print(f"    - Deleted {result_sale_logs.rowcount} SaleLog records.")

        # 2. Delete Sales (depends on Harvests)
        sql_delete_sales = text("DELETE FROM sales;")
        print(f"  - Executing: {sql_delete_sales}")
        result_sales = db.session.execute(sql_delete_sales)
        print(f"    - Deleted {result_sales.rowcount} Sale records.")

        # 3. Delete Harvest Activity Logs (depends on Harvests)
        sql_delete_harvest_logs = text("DELETE FROM harvest_activity_logs;")
        print(f"  - Executing: {sql_delete_harvest_logs}")
        result_harvest_logs = db.session.execute(sql_delete_harvest_logs)
        print(f"    - Deleted {result_harvest_logs.rowcount} HarvestActivityLogs records.")

        # 4. Delete Nutrient Controller Activity Logs (depends on Nutrient Controllers)
        sql_delete_nutrient_logs = text("DELETE FROM nutrient_controller_activity_logs;")
        print(f"  - Executing: {sql_delete_nutrient_logs}")
        result_nutrient_logs = db.session.execute(sql_delete_nutrient_logs)
        print(f"    - Deleted {result_nutrient_logs.rowcount} NutrientControllerActivityLogs records.")

        # 5. Delete Planted Crop Activity Logs (depends on Planted Crops)
        sql_delete_plant_logs = text("DELETE FROM planted_crop_activity_logs;")
        print(f"  - Executing: {sql_delete_plant_logs}")
        result_plant_logs = db.session.execute(sql_delete_plant_logs)
        print(f"    - Deleted {result_plant_logs.rowcount} PlantedCropActivityLogs records.")

        # 6. Delete Harvests (depends on Planted Crops, Users, Greenhouses) - MUST be before Planted Crops
        sql_delete_harvests = text("DELETE FROM harvests;")
        print(f"  - Executing: {sql_delete_harvests}")
        result_harvests = db.session.execute(sql_delete_harvests)
        print(f"    - Deleted {result_harvests.rowcount} Harvest records.")

        # 7. Delete Nutrient Controllers (depends on Planted Crops, Users, Greenhouses) - MUST be before Planted Crops
        sql_delete_nutrients = text("DELETE FROM nutrient_controllers;")
        print(f"  - Executing: {sql_delete_nutrients}")
        result_nutrients = db.session.execute(sql_delete_nutrients)
        print(f"    - Deleted {result_nutrients.rowcount} NutrientController records.")

        # 8. Delete Planted Crops (The base table for many dependencies here. Depends on Greenhouses)
        sql_delete_plants = text("DELETE FROM planted_crops;")
        print(f"  - Executing: {sql_delete_plants}")
        result_plants = db.session.execute(sql_delete_plants)
        print(f"    - Deleted {result_plants.rowcount} PlantedCrops records.")

        # --- Commit Transaction ---
        print("\n  - Committing deletions...")
        db.session.commit()
        print("\n--- Plant, Nutrient, Harvest, and Sales data cleanup completed successfully! ---")
        return True # Indicate success

    except Exception as e:
        db.session.rollback() # Roll back any partial deletions on error
        print(f"\n--- ERROR during raw SQL cleanup ---")
        print(f"An error occurred: {e}")
        # Check if it's a DB constraint error (e.g., FK from another table)
        if "violates foreign key constraint" in str(e).lower():
             print("    HINT: Deletion failed due to a foreign key constraint.")
             print("          Another table not included in this script might still reference")
             print("          one of the tables being deleted (e.g., users, greenhouses).")
             print("          You may need to delete data from that other table first,")
             print("          or adjust the FK constraint (e.g., ON DELETE SET NULL/CASCADE).")
        traceback.print_exc() # Print detailed error information
        return False # Indicate failure
    finally:
        print("--- Finished cleanup script execution attempt. ---")


# --- Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clear ALL plant, nutrient controller, harvest, sales data and associated logs using Raw SQL.",
        formatter_class=argparse.RawTextHelpFormatter
        )
    parser.add_argument(
        '--action',
        type=str,
        choices=['clear_plant_related_raw'], # Updated action choice
        required=True,
        help="Required. Must be 'clear_plant_related_raw' to execute." # Updated help
    )

    args = parser.parse_args()

    print("Acquiring Flask app context...")
    with app.app_context():
        print(f"Context acquired. Executing action: {args.action}")
        if args.action == 'clear_plant_related_raw':
            success = clear_plant_related_data_raw_sql() # Call the updated function
            if success:
               print("\nPlant, Nutrient, Harvest & Sales data clearing process finished successfully.")
            else:
               print("\nPlant, Nutrient, Harvest & Sales data clearing process failed or was aborted.")
        else:
            print("Invalid action specified.")
        print("Releasing Flask app context.")
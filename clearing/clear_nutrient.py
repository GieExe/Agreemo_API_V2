#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\clear_nutrient.py

import sys
import os
import argparse
import traceback
from sqlalchemy import text  # For raw SQL

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
# We technically don't NEED the models for raw SQL delete,
# but keeping them doesn't hurt and might be useful for other potential functions.
try:
    from models.nutrient_controllers_model import NutrientController
    from models.activity_logs.nutrient_controller_activity_logs_model import NutrientControllerActivityLogs
except ImportError as e:
    # Log the error but proceed, as raw SQL doesn't strictly need the ORM models here
    print(f"Warning: Could not import some models: {e}. Proceeding with raw SQL.")
    # Define as None to avoid NameError if used elsewhere accidentally
    NutrientController = None
    NutrientControllerActivityLogs = None


# --- Data Cleanup Function for Nutrient Controllers & Logs using Raw SQL ---
def clear_nutrient_data_raw_sql():
    """
    Deletes ALL data from nutrient_controllers and nutrient_controller_activity_logs
    tables using RAW SQL.
    This bypasses SQLAlchemy ORM relationship checks. Use with extreme caution!
    """
    print(f"--- Starting Nutrient Controller Data Cleanup (using Raw SQL) ---")
    print("    WARNING: This will delete ALL nutrient controller data and logs.")

    # Safety confirmation prompt
    confirm = input("    Type 'DELETE ALL NUTRIENT DATA RAW' exactly to confirm: ")
    if confirm != "DELETE ALL NUTRIENT DATA RAW":
        print("    Cleanup aborted by user.")
        return False  # Indicate abortion

    try:
        print("\n[Deletion] Starting deletion process (raw SQL, respecting FKs)...")

        # --- Execute RAW SQL DELETE statements ---

        # 1. Delete Nutrient Controller Activity Logs (depends on NutrientControllers)
        sql_delete_nutrient_logs = text("DELETE FROM nutrient_controller_activity_logs;")
        print(f"  - Executing: {sql_delete_nutrient_logs}")
        result_nutrient_logs = db.session.execute(sql_delete_nutrient_logs)
        print(f"    - Deleted {result_nutrient_logs.rowcount} NutrientControllerActivityLogs records.")

        # 2. Delete Nutrient Controllers (last in this chain)
        sql_delete_nutrient_controllers = text("DELETE FROM nutrient_controllers;")
        print(f"  - Executing: {sql_delete_nutrient_controllers}")
        result_nutrient_controllers = db.session.execute(sql_delete_nutrient_controllers)
        print(f"    - Deleted {result_nutrient_controllers.rowcount} NutrientController records.")

        # --- Commit Transaction ---
        print("  - Committing deletions...")
        db.session.commit()
        print("\n--- Nutrient Controller data cleanup completed successfully! ---")
        return True  # Indicate success

    except Exception as e:
        db.session.rollback()  # Roll back any partial deletions on error
        print(f"\n--- ERROR during raw SQL cleanup ---")
        print(f"An error occurred: {e}")
        # Check if it's a DB constraint error (e.g., FK from another table)
        if "violates foreign key constraint" in str(e).lower():
            print("    HINT: Deletion failed due to a foreign key constraint.")
            print("          Another table might still reference one of the deleted tables.")
            print("          You may need to delete data from that other table first.")
        traceback.print_exc()  # Print detailed error information
        return False  # Indicate failure
    finally:
        print("--- Finished cleanup script execution attempt. ---")


# --- Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clear ALL nutrient controller data and associated logs using Raw SQL.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--action',
        type=str,
        choices=['clear_nutrient_raw'],  # Updated action choice
        required=True,
        help="Required. Must be 'clear_nutrient_raw' to execute."  # Updated help
    )

    args = parser.parse_args()

    print("Acquiring Flask app context...")
    with app.app_context():
        print(f"Context acquired. Executing action: {args.action}")
        if args.action == 'clear_nutrient_raw':
            success = clear_nutrient_data_raw_sql()  # Call the updated function
            if success:
                print("Nutrient controller data clearing process finished successfully.")
            else:
                print("Nutrient controller data clearing process failed or was aborted.")
        else:
            print("Invalid action specified.")
        print("Releasing Flask app context.")
# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\clearing\clear_rejection.py
import sys
import os
import argparse
import traceback
from sqlalchemy import text # For raw SQL

# --- Project Setup ---
# Adjust the path calculation if this script is located differently relative to the project root
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.')) # Assuming script is in project root
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Flask App and DB ---
try:
    from app import app # Assuming your Flask app instance is named 'app' in 'app.py' or '__init__.py'
    from db import db
except ImportError as e:
    print(f"Error importing Flask app or db instance: {e}")
    print("Please ensure the script is run from the correct directory or PYTHONPATH is set.")
    sys.exit(1)

# --- Model Imports ---
# Optional: Import models for reference, though not strictly needed for raw SQL delete.
try:
    from models.reason_for_rejection_model import ReasonForRejection
    from models.activity_logs.rejection_activity_logs_model import RejectionActivityLogs
except ImportError as e:
    print(f"Warning: Could not import some models: {e}. Proceeding with raw SQL.")
    ReasonForRejection = None
    RejectionActivityLogs = None


# --- Data Cleanup Function for Rejection & Logs using Raw SQL ---
def clear_rejection_data_raw_sql():
    """
    Deletes ALL data from reason_for_rejection and rejection_activity_logs
    tables using RAW SQL.
    This bypasses SQLAlchemy ORM relationship checks. Use with extreme caution!
    """
    print(f"--- Starting Rejection Data Cleanup (using Raw SQL) ---")
    print("    WARNING: This will delete ALL rejection reasons and rejection logs.")

    try:
        print("\n[Deletion] Starting deletion process (raw SQL, respecting FKs)...")

        # --- Execute RAW SQL DELETE statements ---
        # NOTE: The order matters due to Foreign Key constraints.
        # Delete logs first, as they reference the main rejection table.

        # 1. Delete Rejection Activity Logs (depends on ReasonForRejection)
        sql_delete_rejection_logs = text("DELETE FROM rejection_activity_logs;")
        print(f"  - Executing: {sql_delete_rejection_logs}")
        result_rejection_logs = db.session.execute(sql_delete_rejection_logs)
        print(f"    - Deleted {result_rejection_logs.rowcount} RejectionActivityLogs records.")

        # 2. Delete Reason For Rejection records (main table)
        sql_delete_rejections = text("DELETE FROM reason_for_rejection;")
        print(f"  - Executing: {sql_delete_rejections}")
        result_rejections = db.session.execute(sql_delete_rejections)
        print(f"    - Deleted {result_rejections.rowcount} ReasonForRejection records.")

        # --- Commit Transaction ---
        print("  - Committing deletions...")
        db.session.commit()
        print("\n--- Rejection data cleanup completed successfully! ---")
        return True # Indicate success

    except Exception as e:
        db.session.rollback() # Roll back any partial deletions on error
        print(f"\n--- ERROR during raw SQL cleanup ---")
        print(f"An error occurred: {e}")
        # Check if it's a DB constraint error (e.g., FK from another table)
        if "violates foreign key constraint" in str(e).lower():
             print("    HINT: Deletion failed due to a foreign key constraint.")
             print("          Another table might still reference one of the deleted tables.")
             print("          You may need to delete data from that other table first.")
        traceback.print_exc() # Print detailed error information
        return False # Indicate failure
    finally:
        print("--- Finished cleanup script execution attempt. ---")


# --- Script Execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clear ALL rejection data and associated logs using Raw SQL.",
        formatter_class=argparse.RawTextHelpFormatter
        )
    parser.add_argument(
        '--action',
        type=str,
        choices=['clear_rejection_raw'], # Action specific to this script
        required=True,
        help="Required. Must be 'clear_rejection_raw' to execute."
    )

    args = parser.parse_args()

    print("Acquiring Flask app context...")
    with app.app_context():
        print(f"Context acquired. Executing action: {args.action}")
        if args.action == 'clear_rejection_raw':
            success = clear_rejection_data_raw_sql() # Call the rejection cleanup function
            if success:
               print("Rejection data clearing process finished successfully.")
            else:
               print("Rejection data clearing process failed or was aborted.")
        else:
            # This case shouldn't be reachable due to 'choices' in argparse
            print("Invalid action specified.")
        print("Releasing Flask app context.")
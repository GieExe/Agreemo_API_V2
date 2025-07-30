# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\firebase_listener.py
import firebase_admin
from firebase_admin import credentials, db as firebase_db
import time
import os
import traceback  # Import traceback module

def firebase_control_listener(app, event):
    """Callback function for Firebase changes. Logs the data directly."""

    pid = os.getpid()
    print(f"DEBUG (PID {pid}): firebase_control_listener called")
    print(f"DEBUG (PID {pid}): Event: {event.event_type}, Path: {event.path}, Data: {event.data}")

    current_data = event.data  # Get the data from the event

    if current_data:
        print(f"DEBUG (PID {pid}): Logging current data: {current_data}")
    else:
        print(f"DEBUG (PID {pid}): No data received from Firebase.")


def init_firebase_listener(app):
    """Initializes and starts the Firebase listener."""
    print("DEBUG: Initializing Firebase listener...")
    CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
    DATABASE_URL = os.environ.get("DATABASE_URL")

    print(f"DEBUG: Credentials Path: {CREDENTIALS_PATH}") #ADDED for Debug

    if not firebase_admin._apps:
        print("DEBUG: Firebase app not yet initialized.")  # ADDED
        try:
            cred_object = credentials.Certificate(CREDENTIALS_PATH)
            if not DATABASE_URL:
                raise ValueError("DATABASE_URL environment variable not set.")
            firebase_admin.initialize_app(cred_object, {'databaseURL': DATABASE_URL})
            print("DEBUG: Firebase app initialized successfully.")  # ADDED
        except Exception as e:
            error_message = f"Firebase initialization failed: {e}"
            print(f"ERROR: {error_message}")
            traceback_message = traceback.format_exc()  # Get the traceback as a string
            print(f"TRACEBACK: {traceback_message}")

            # Store the error information in the Flask app's config,
            # where it can be accessed by the route.
            app.config['FIREBASE_INIT_ERROR'] = error_message
            app.config['FIREBASE_INIT_TRACEBACK'] = traceback_message
            return  # Very important: exit the function on failure!

    firebase_db.reference("pumpControl").listen(lambda event: firebase_control_listener(app, event))
    print("DEBUG: Firebase listener started.")
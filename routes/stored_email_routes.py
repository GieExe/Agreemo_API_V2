# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\stored_email_routes.py
from flask import Blueprint, request, jsonify
import os
from db import db  # Assuming 'db' is your SQLAlchemy instance initialized elsewhere
from models.stored_email_model import StoredEmail # Import the model

stored_email_api = Blueprint("stored_email_api", __name__)

# Retrieve API Key from environment variables for security
API_KEY = os.environ.get("API_KEY")

# --- Helper Function for API Key Check ---
def check_api_key():
    """Checks if the provided API key in the header is valid."""
    api_key_header = request.headers.get("x-api-key")
    if api_key_header != API_KEY:
        return jsonify(
            error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct api_key."}
        ), 403
    return None # Return None if authorized

# --- GET Route: Retrieve all stored emails ---
@stored_email_api.get("/stored-email")
def stored_email_all_data():
    """Retrieves all stored email records."""
    # Check API Key
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    try:
        # Query all records from the StoredEmail table
        query_data = StoredEmail.query.all()

        # Check if any data was found
        if not query_data:
            return jsonify(message="No stored email data found."), 404

        # Format the data into a list of dictionaries
        stored_email_dict = [{
            "stored_email_id": data.stored_email_id,
            "email": data.email
        } for data in query_data]

        # Return the list as a JSON response
        return jsonify(stored_email_dict), 200

    except Exception as e:
        # Generic error handling for unexpected issues
        print(f"Error in GET /stored-email: {e}") # Log the error server-side
        return jsonify(error={"message": f"An error occurred retrieving data: {str(e)}"}), 500

# --- POST Route: Add a new stored email (using form data) ---
@stored_email_api.post("/stored-email")
def add_stored_email():
    """Adds a new email to the stored email list, expecting form data."""
    # Check API Key
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    try:
        # Get email from form data instead of JSON
        email = request.form.get("email") # Changed from request.get_json()

        # Check if email was provided in the form data
        if not email:
            return jsonify(error={"message": "Invalid input: 'email' field is required in form data."}), 400

        # --- Input Validation (Basic) ---
        # Ensure email is a string and contains '@'
        if not isinstance(email, str) or "@" not in email:
             return jsonify(error={"message": "Invalid input: 'email' must be a valid email string."}), 400

        # Check if email already exists (case-insensitive check might be better depending on needs)
        # Consider using .ilike() for case-insensitive comparison if needed:
        # existing_email = StoredEmail.query.filter(StoredEmail.email.ilike(email)).first()
        existing_email = StoredEmail.query.filter(StoredEmail.email == email).first()
        if existing_email:
            return jsonify(error={"message": f"Conflict: Email '{email}' already exists."}), 409 # 409 Conflict

        # Create a new StoredEmail object
        new_email = StoredEmail(email=email)

        # Add the new record to the database session
        db.session.add(new_email)
        # Commit the transaction to save the changes
        db.session.commit()

        # Return the newly created email details with a 201 Created status
        return jsonify({
            "message": "Stored email added successfully.",
            "stored_email": {
                "stored_email_id": new_email.stored_email_id,
                "email": new_email.email
            }
        }), 201 # 201 Created

    except Exception as e:
        # Rollback the session in case of any error during the transaction
        db.session.rollback()
        print(f"Error in POST /stored-email: {e}") # Log the error server-side
        return jsonify(error={"message": f"Failed to add stored email. Error: {str(e)}"}), 500


# --- DELETE Route: Delete a specific stored email by ID ---
@stored_email_api.delete("/stored-email/<int:stored_email_id>")
def delete_stored_email(stored_email_id):
    """Deletes a stored email record by its ID."""
    # Check API Key
    auth_error = check_api_key()
    if auth_error:
        return auth_error

    try:
        # Find the email record by its primary key
        stored_email = StoredEmail.query.get(stored_email_id)

        # If the record doesn't exist, return a 404 Not Found error
        if not stored_email:
            return jsonify(error={"message": f"Stored email with ID {stored_email_id} not found."}), 404

        # Delete the record from the database session
        db.session.delete(stored_email)
        # Commit the transaction to save the changes
        db.session.commit()

        # Return a success message
        return jsonify(message=f"Stored email with ID {stored_email_id} deleted successfully."), 200

    except Exception as e:
        # Rollback the session in case of any error during the transaction
        db.session.rollback()
        print(f"Error in DELETE /stored-email/{stored_email_id}: {e}") # Log the error server-side
        return jsonify(error={"message": f"Failed to delete stored email. Error: {str(e)}"}), 500

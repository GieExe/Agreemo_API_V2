#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\routes\user_routes.py
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz
from flask import Blueprint, request, jsonify, render_template
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from passlib.handlers.pbkdf2 import pbkdf2_sha256

from db import db
from forms import ChangePasswordForm
from functions import log_activity
from models import Greenhouse, Users, AdminUser
from models.activity_logs.rejection_activity_logs_model import RejectionActivityLogs
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

from models.activity_logs.user_activity_logs_model import UserActivityLogs

users_api = Blueprint("users_api", __name__)

API_KEY = os.environ.get("API_KEY")

MY_EMAIL = os.environ.get('EMAIL')
MY_PASSWORD = os.environ.get("PASSWORD")
BASE_URL = os.environ.get("BASE_URL")

s = URLSafeTimedSerializer('Thisisasecret!')


# Get all user data
@users_api.get("/users")
def users_data():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorised": "Invalid API Key"}), 403

        query_data = Users.query.all()

        if not query_data:
            return jsonify(message="No user data found."), 404

        users_dict = [{
            "user_id": data.user_id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "date_of_birth": data.date_of_birth,
            "email": data.email,
            "phone_number": data.phone_number,
            "address": data.address,
            "isAdmin": data.isAdmin,
            "isActive": data.isActive,
            "isNewUser": data.isNewUser
        } for data in query_data]

        return jsonify(users_dict), 200

    except Exception as e:
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@users_api.post("/user")
def add_user():
    try:
        # Check API key for authorization
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        # Extract form data
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        date_of_birth = request.form.get("date_of_birth")
        email = request.form.get("email")
        phone_number = request.form.get("phone_number")
        address = request.form.get("address")

        # Validate required fields
        if not first_name or not last_name or not email:
            return jsonify(error={"message": "First name, last name, and email are required fields."}), 400

        # Check if email already exists
        existing_user = Users.query.filter_by(email=email).first()
        if existing_user:
            return jsonify(error={"message": "Email already exists."}), 400 # 400 is correct for client error

        existing_phone_num = Users.query.filter_by(phone_number=phone_number).first()
        if existing_phone_num:
            return jsonify(error={"message": "Mobile number already exists."}), 409  # 409 Conflict

        # Convert date_of_birth to a date object if provided
        dob = None
        if date_of_birth:
            try:
                dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            except ValueError:
                return jsonify(error={"message": "Invalid date format for date_of_birth. Use YYYY-MM-DD."}), 400

        # Create a new user instance
        new_user = Users(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            email=email,
            phone_number=phone_number,
            address=address,
            password=pbkdf2_sha256.hash(phone_number)
        )

        # Add and commit new user to the database
        db.session.add(new_user)
        db.session.commit()

        send_email(email)  # Still sending welcome/initial credentials email

        log_activity(UserActivityLogs, login_id=new_user.user_id, logs_description="User successfully added!")

        return jsonify(message="User successfully added!", user_id=new_user.user_id), 201  # Return success response

    except Exception as e:
        db.session.rollback()  # Rollback in case of any other errors
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


def send_email(email):
    subject = 'Login Details'
    body = f"""
    <html>
    <head>
        <style>
            /* ... your existing CSS styles ... */
             body {{
                font-family: Arial, sans-serif;
                background-color: #f7f7f7;
                padding: 20px;
                margin: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                padding: 40px;
            }}
            h1 {{
                font-size: 24px;
                color: #333;
            }}
            p {{
                font-size: 16px;
                color: #666;
                margin-bottom: 20px;
            }}
            a {{
                color: #007bff;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            .password {{
                font-size: 20px;
                color: #333;
                margin-top: 20px;
            }}
            .footer {{
                text-align: center;
                margin-top: 40px;
                font-size: 14px;
                color: #999;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <p>Login Details</p>
            <p>Email: {email}</p>
            <p>Password: your password is your mobile number</p>

        </div>
        <div class="footer">
            AGREEMO @ 2025
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg.attach(MIMEText(body, 'html'))  # Set the message type to HTML
    msg['Subject'] = subject
    msg['From'] = MY_EMAIL
    msg['To'] = email

    # Connect to the SMTP server and send the email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MY_EMAIL, MY_PASSWORD)
            server.sendmail(MY_EMAIL, [email], msg.as_string())

        print("Initial credentials email sent successfully")  # Better message
    except Exception as e:
        print(f"Failed to send initial credentials email. Error: {str(e)}")


# Delete all
@users_api.delete("/users")
def delete_all_users():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        # Delete all users from the database
        num_deleted = Users.query.delete()
        db.session.commit()

        return jsonify(message=f"Successfully deleted {num_deleted} users."), 200

    except Exception as e:
        db.session.rollback()  # Rollback changes in case of error
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


# delete by user_id
@users_api.delete("/user/<int:user_id>")
def delete_user(user_id):
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        # Find the user by ID
        user = Users.query.get(user_id)

        if not user:
            return jsonify(error={"message": "User not found"}), 404

        # Delete the user
        db.session.delete(user)
        db.session.commit()

        return jsonify(message=f"Successfully deleted user with id {user_id}."), 200 # Include user_id

    except Exception as e:
        db.session.rollback()  # Rollback changes in case of error
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@users_api.post("/user/login")
def user_login():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        user = Users.query.filter_by(email=email).first()

        if not user:
            log_activity(UserActivityLogs, login_id=None, logs_description=f"Failed login attempt with non-existent email: {email}")
            return jsonify(error={"message": "Email doesn't exist."}), 400

        # Check if the password is incorrect
        if not pbkdf2_sha256.verify(request.form.get("password"), user.password):
            # If the account is currently locked, extend the lock period immediately
            if user.failed_timer and datetime.now() < user.failed_timer:
                if user.consecutive_failed_login is None:
                    user.consecutive_failed_login = 0
                user.consecutive_failed_login += 1
                user.failed_timer = datetime.now() + timedelta(seconds=30)  # Extend by 30 seconds
                log_activity(
                    UserActivityLogs,
                    login_id=user.user_id,
                    logs_description=f"Invalid Credential.  Attempt #{user.consecutive_failed_login}" # Clearer log
                )
                db.session.commit()  # Save changes to the database
                return jsonify(
                    error={"message": f"Invalid Credentials. Account locked. Try again in 30 seconds."} #Clearer message
                ), 423  # 423 Locked

            # Not currently locked, so process a normal failed attempt
            if user.consecutive_failed_login is None:
                user.consecutive_failed_login = 0
            user.consecutive_failed_login += 1

            # Lock the account if the count reaches 3 or more
            if user.consecutive_failed_login >= 3:
                user.failed_timer = datetime.now() + timedelta(seconds=30)
                log_activity(
                    UserActivityLogs,
                    login_id=user.user_id,
                    logs_description=f"Invalid Credentials. Account locked after {user.consecutive_failed_login} attempts." # Clearer log
                )
                # Removed send_login_attempt_notification(user.email)  <-- NO EMAIL ON FAILED ATTEMPT

                db.session.commit()  # Save changes
                return jsonify(
                    error={"message": f"Invalid Credentials. Account locked. Try again in 30 seconds."} #Clearer message
                ), 423   # 423 Locked

            db.session.commit() # Save after incrementing failed attempts
            log_activity(
                UserActivityLogs,
                login_id=user.user_id,
                logs_description=f"Invalid Credential. Attempt #{user.consecutive_failed_login}" # Clearer log
            )
            return jsonify(error={"message": "Invalid Credentials."}), 401  # Unauthorized

        # Additional checks if password is correct
        if user.isNewUser:
            log_activity(
                UserActivityLogs,
                login_id=user.user_id,
                logs_description="New user, please change your password." # Clearer log
            )
            return jsonify(error={"message": "New user, please change your password."}), 403  # 403 Forbidden

        if not user.isActive:
            log_activity(
                UserActivityLogs,
                login_id=user.user_id,
                logs_description="User account is not active."
            )
            return jsonify(error={"message": "User account is not active."}), 403 # 403 Forbidden

        # Successful login: reset failed login counters and timer
        user.consecutive_failed_login = 0  # Reset to 0 on success
        user.failed_timer = None
        db.session.commit()  # commit the reset

        user_data = {
            "login_id": user.user_id,
            "full_name": f"{user.first_name} {user.last_name}",  # Consistent naming
            "email": user.email
        }

        log_activity(
            UserActivityLogs,
            login_id=user.user_id,
            logs_description="Login successful"
        )

        return jsonify(user_data), 200

    except Exception as e:
        return jsonify(error={"message": f"Failed to login. Error: {str(e)}"}), 500


@users_api.post("/user/logout")
def user_logout():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"message": "Not Authorized", "details": "Invalid API Key"}), 403

        email = request.form.get("email")

        if not email:
            return jsonify(error={"message": "Email is required."}), 400 # 400 Bad Request

        query_data = Users.query.filter_by(email=email).first()

        if query_data is None:
            return jsonify(error={"message": "Email not found."}), 404

        log_activity(UserActivityLogs, login_id=query_data.user_id, logs_description="Logout successful") # Clearer log
        return jsonify(success={"message": "Successfully logged out."}), 200

    except Exception as e:
        return jsonify(error={"message": f"Failed to logout. Error: {str(e)}"}), 500


# change password
@users_api.put("/user/change-password")
def user_change_password():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        user_to_change_pass = Users.query.filter_by(email=email).first()

        if not user_to_change_pass:
            return jsonify(error={"message": "Email not found"}), 404

        old_password = request.form.get("old_password")
        if not old_password:
            return jsonify(error={"message": "Old password is required."}), 400

        if not pbkdf2_sha256.verify(old_password, user_to_change_pass.password):
            return jsonify(error={"message": "Incorrect old password."}), 400

        new_password = request.form.get("new_password")
        if not new_password:
            return jsonify(error={"message": "New password is required."}), 400

        if pbkdf2_sha256.verify(new_password, user_to_change_pass.password):
            return jsonify(error={"message": "New password cannot be the same as the old password."}), 400

        user_to_change_pass.password = pbkdf2_sha256.hash(new_password)
        db.session.commit()

        # Log successful password change
        log_activity(UserActivityLogs, login_id=user_to_change_pass.user_id,
                     logs_description="Password changed successfully.")


        user_data = {
            "login_id": user_to_change_pass.user_id,
            "full_name": f"{user_to_change_pass.first_name} {user_to_change_pass.last_name}", # Consistent naming
            "email": user_to_change_pass.email
        }

        return jsonify(message="Password changed successfully.", user_data=user_data), 200 # Added message

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"Failed to update user password. Error: {str(e)}"}), 500


# forgot password
@users_api.post("/user/forgot-pass")  # Changed to /forgot-pass for clarity
def user_forgot_password():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        existing_user = Users.query.filter_by(email=email).first()

        if not existing_user:
            return jsonify(error={"message": "Email not found."}), 400 # Consistent with other not found errors

        reset_token = s.dumps(email, salt='password-reset')

        send_reset_email(email, reset_token, existing_user.first_name)  # Use first_name for personalized email

        log_activity(UserActivityLogs, login_id=existing_user.user_id,
                     logs_description="Password reset link sent.")  #Simplified log

        return jsonify(success={"message": "Reset link sent to your email."}), 200 # Simplified success message

    except Exception as e:
        return jsonify(error={"message": f"Failed to initiate password reset. Error: {str(e)}"}), 500



def send_reset_email(email, reset_token, name):
    subject = 'Password Reset'
    reset_link = f"{BASE_URL}/user/{reset_token}" # Use BASE_URL
    body = f"""
        <html>
        <head>
            <style>
                /* ... your existing CSS styles ... */
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f7f7f7;
                    padding: 20px;
                    margin: 0;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #fff;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    padding: 40px;
                }}
                h1 {{
                    font-size: 24px;
                    color: #333;
                }}
                p {{
                    font-size: 16px;
                    color: #666;
                    margin-bottom: 20px;
                }}
                a {{
                    color: #007bff;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                .password {{
                    font-size: 20px;
                    color: #333;
                    margin-top: 20px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    font-size: 14px;
                    color: #999;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Dear {name},</h1>
                <p>Click the following link to reset your password: <a href="{reset_link}">Reset Password</a></p>

            </div>
            <div class="footer">
                AGREEMO @ 2025
            </div>
        </body>
        </html>
        """

    msg = MIMEMultipart()
    msg.attach(MIMEText(body, 'html'))  # Set the message type to HTML
    msg['Subject'] = subject
    msg['From'] = MY_EMAIL
    msg['To'] = email

    # Connect to the SMTP server and send the email
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MY_EMAIL, MY_PASSWORD)
            server.sendmail(MY_EMAIL, [email], msg.as_string())

        print("Reset email sent successfully")
    except Exception as e:
        print(f"Failed to send reset email. Error: {str(e)}")


@users_api.route("/user/<token>", methods=['GET', 'POST'])
def user_link_forgot_password(token):
    form = ChangePasswordForm()
    try:
        email = s.loads(token, salt='password-reset', max_age=1800) # 30 minutes

        user = Users.query.filter_by(email=email).first()

        if user:
            if form.validate_on_submit():
                user.password = pbkdf2_sha256.hash(form.new_password.data)
                #  New User
                user.isNewUser = False  # Mark as no longer a new user.
                db.session.commit()

                # Log successful password reset via token
                log_activity(UserActivityLogs, login_id=user.user_id,
                             logs_description="Password reset via token successful.")

                return ('<h1 style="font-family: Arial, sans-serif; font-size: 24px; color: #333; text-align: center; '
                        'margin-top: 50px;">Password reset successfully!</h1>') # Clear message
            else:
                return render_template("reset_password.html", form=form, token=token)  # Pass token to template
        else:
            return jsonify(error={"message": "Invalid or expired token."}), 400 # 400 Bad Request

    except SignatureExpired:
        return '<h1 style="font-family: Arial, sans-serif; font-size: 24px; color: #333; text-align: center; margin-top: 50px;">Token has expired.</h1>', 410  # 410 Gone
    except Exception as e:
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@users_api.put("/new-user/change-password")
def new_user_change_password():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        user_to_change_pass = Users.query.filter_by(email=email).first()

        if not user_to_change_pass:
            return jsonify(error={"message": "Email not found"}), 404

        # Validate new password
        new_password = request.form.get("new_password")
        if not new_password:
            return jsonify(error={"message": "New password is required."}), 400

        # Update the password if a new password is provided
        user_to_change_pass.password = pbkdf2_sha256.hash(new_password)
        user_to_change_pass.isActive = True
        user_to_change_pass.isNewUser = False

        # Commit the changes to the database
        db.session.commit()

        log_activity(UserActivityLogs, login_id=user_to_change_pass.user_id,
                     logs_description="Initial password change successful.") # Specific log

        user_data = {
            "login_id": user_to_change_pass.user_id,
            "full_name": f"{user_to_change_pass.first_name} {user_to_change_pass.last_name}", #Consistent naming
            "email": user_to_change_pass.email
        }

        return jsonify(message="Password changed successfully.", user_data=user_data), 200 # Added message

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"Failed to update user password. Error: {str(e)}"}), 500

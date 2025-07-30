# C:\Users\Giebert\PycharmProjects\agreemo_api\routes\admin_routes.py
import os
import pytz
from flask import Blueprint, request, jsonify, render_template
from flask_login import logout_user  # Although imported, it isn't directly used in this admin context.
from db import db
from functions import log_activity
from models import AdminUser, Users
from forms import ChangePasswordForm
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import smtplib
from passlib.hash import pbkdf2_sha256
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart

from models.activity_logs.admin_activity_logs_model import AdminActivityLogs
from models.activity_logs.user_activity_logs_model import UserActivityLogs

admin_api = Blueprint("admin_api", __name__)

API_KEY = os.environ.get("API_KEY")
MY_EMAIL = os.environ.get('EMAIL')
MY_PASSWORD = os.environ.get("PASSWORD")
BASE_URL = os.environ.get("BASE_URL")

s = URLSafeTimedSerializer('Thisisasecret!')  # For password reset tokens


def get_manila_now():
    ph_tz = pytz.timezone('Asia/Manila')
    manila_now = datetime.now(ph_tz)
    return manila_now.replace(tzinfo=None)  # Make it naive (remove timezone info)


# --- Existing get routes ...
@admin_api.get("/admin")
def get_all_admin_data():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        query_data = AdminUser.query.all()

        if not query_data:
            return jsonify(message="No admin data found."), 404

        admin_dict = [{
            "login_id": data.login_id,
            "name": data.name,
            "is_disabled": data.is_disabled,
            "email": data.email
        } for data in query_data]

        return jsonify(admin_dict), 200

    except Exception as e:
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@admin_api.post("/admin/add")
def admin_add():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        existing_admin = AdminUser.query.filter_by(email=email).first()

        if existing_admin:
            return jsonify(error={"message": "Email already exists."}), 400

        new_admin = AdminUser(
            name=request.form.get("name"),
            email=email,
            is_disabled=False,
            password=pbkdf2_sha256.hash(request.form.get("password")),
        )

        db.session.add(new_admin)
        db.session.commit()

        return jsonify(message="Admin user successfully added!"), 201

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"Failed to register. Error: {str(e)}"}), 500


def send_login_attempt_notification(email, username, reset_token):
    subject = 'Multiple Failed Login Attempts'
    reset_link = f"{BASE_URL}/admin/{reset_token}"  # Create the reset link
    body = f"""
    <html>
    <head>
       <style>
            /* -- Existing HTML Format -- */
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
            <h1>Security Alert</h1>
            <p>Dear, {username} We detected multiple failed login attempts on your account. Your account has been temporarily locked for security reasons.</p>
            <p>If this was you, please wait 30 seconds before trying to log in again.</p>
            <p>If this was not you, please reset your password immediately by clicking this link: <a href="{reset_link}">Reset Password</a></p>
        </div>
        <div class="footer">
            AGREEMO @ 2025
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg.attach(MIMEText(body, 'html'))
    msg['Subject'] = subject
    msg['From'] = MY_EMAIL
    msg['To'] = email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MY_EMAIL, MY_PASSWORD)
            server.sendmail(MY_EMAIL, [email], msg.as_string())

        print("Login attempt notification email sent successfully.")

    except Exception as e:
        print(f"Failed to send login attempt notification email. Error: {str(e)}")


# Admin Login
@admin_api.post("/admin/login")
def login_admin():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        user = AdminUser.query.filter_by(email=email).first()

        if not user:
            log_activity(AdminActivityLogs, login_id=None,
                         logs_description=f"Failed login attempt with non-existent email: {email}")
            return jsonify(error={"message": "Email doesn't exist."}), 400  # Corrected status code

        if user.is_disabled:
            if user.failed_timer and datetime.now() < user.failed_timer:
                remaining_time = (user.failed_timer - datetime.now()).seconds
                return jsonify(error={"message": f"Account is temporarily locked. Try again in {remaining_time} seconds."}), 423  # 423 Locked
            else:
                user.is_disabled = False
                user.consecutive_failed_login = 0
                user.failed_timer = None
                db.session.commit()

        if not pbkdf2_sha256.verify(request.form.get("password"), user.password):
            user.consecutive_failed_login = (user.consecutive_failed_login or 0) + 1

            if user.consecutive_failed_login >= 3:
                user.failed_timer = datetime.now() + timedelta(seconds=30)
                user.is_disabled = True
                db.session.commit()

                log_activity(AdminActivityLogs, login_id=user.login_id,
                             logs_description=f"Invalid Credentials {user.consecutive_failed_login} times. Account locked for 30 seconds.")
                # Generate reset token *before* sending the email
                reset_token = s.dumps(email, salt='password-reset')
                send_login_attempt_notification(user.email, user.name, reset_token)

                return jsonify(error={"message": f"Too many failed attempts. Account locked for 30 seconds."}), 423  # 423 Locked
            db.session.commit()
            log_activity(AdminActivityLogs, login_id=user.login_id,
                         logs_description=f"Invalid Credentials {user.consecutive_failed_login} times.")
            return jsonify(error={"message": "Invalid Credentials."}), 401  # Unauthorized

        # Successful Login
        user.consecutive_failed_login = 0
        user.failed_timer = None
        user.is_disabled = False
        db.session.commit()

        user_data = {
            "login_id": user.login_id,
            "name": user.name,
            "email": user.email
        }

        log_activity(AdminActivityLogs, login_id=user.login_id, logs_description="Login successful")
        return jsonify(success={"message": "Login successful", "user_data": user_data}), 200

    except Exception as e:
        return jsonify(error={"message": f"Failed to login. Error: {str(e)}"}), 500


@admin_api.post("/admin/activate")
def activate_user():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        admin_email = request.form.get("admin_email")
        admin_user = AdminUser.query.filter_by(email=admin_email).first()
        if not admin_user:
            return jsonify(error={"message": "Admin not found."}), 404

        user_email = request.form.get("user_email")
        user = Users.query.filter_by(email=user_email).first()
        if not user:
            return jsonify(error={"message": "User not found"}), 404

        user.isActive = True
        db.session.commit()

        now = get_manila_now()

        admin_log = AdminActivityLogs(
            login_id=admin_user.login_id,
            logs_description=f"Activated user {user.first_name} {user.last_name}.",
            log_date=now
        )
        db.session.add(admin_log)
        db.session.commit()

        return jsonify(message="Successfully activated."), 200

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@admin_api.post("/admin/deactivate")
def deactivate_user():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        admin_email = request.form.get("admin_email")
        admin_user = AdminUser.query.filter_by(email=admin_email).first()
        if not admin_user:
            return jsonify(error={"message": "Admin not found."}), 404

        user_email = request.form.get("user_email")
        user = Users.query.filter_by(email=user_email).first()
        if not user:
            return jsonify(error={"message": "User not found"}), 404

        user.isActive = False
        db.session.commit()

        now = get_manila_now()

        admin_log = AdminActivityLogs(
            login_id=admin_user.login_id,
            logs_description=f"Deactivated user {user.first_name} {user.last_name}.",
            log_date=now
        )
        db.session.add(admin_log)

        user_logout_log = UserActivityLogs(
            login_id=user.user_id,
            logs_description="logout",  # Could be more specific, e.g., "forced logout by admin"
            log_date=now
        )
        db.session.add(user_logout_log)
        db.session.commit()

        return jsonify(message="Successfully deactivated."), 200

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


# change password
@admin_api.put("/admin")
def admin_change_password():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        user_to_change_pass = AdminUser.query.filter_by(email=email).first()

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

        # Log the password change
        now = get_manila_now()
        log_activity(AdminActivityLogs, login_id=user_to_change_pass.login_id,
                     logs_description=f"Changed Password on {now.strftime('%Y-%m-%d %H:%M:%S')}")


        user_data = {
            "login_id": user_to_change_pass.login_id,
            "name": user_to_change_pass.name,
            "email": user_to_change_pass.email
        }

        return jsonify(success={"message": "Successfully changed the password.", "user_data": user_data}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"Failed to update user password. Error: {str(e)}"}), 500




# forgot password
@admin_api.post("/admin")  
def admin_forgot_password():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorised": "Invalid API Key"}), 403

        email = request.form.get("email")
        existing_admin = AdminUser.query.filter_by(email=email).first()

        if not existing_admin:
            return jsonify(error={"message": "Email not found."}), 400 # Changed to 400 for consistency

        reset_token = s.dumps(email, salt='password-reset')
        send_reset_email(email, reset_token, existing_admin.name)

        log_activity(AdminActivityLogs, login_id=existing_admin.login_id,
                     logs_description="Reset password link sent.")  # Simplified log message

        return jsonify(success={"message": "Reset link sent to your email."}), 200

    except Exception as e:
        return jsonify(error={"message": f"Failed to initiate password reset. Error: {str(e)}"}), 500


def send_reset_email(email, reset_token, name):
    subject = 'Password Reset'
    reset_link = f"{BASE_URL}/admin/{reset_token}"  # Use BASE_URL for consistency
    body = f"""
        <html>
        <head>
            <style>
                /* -- Existing CSS -- */
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
    msg.attach(MIMEText(body, 'html'))
    msg['Subject'] = subject
    msg['From'] = MY_EMAIL
    msg['To'] = email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(MY_EMAIL, MY_PASSWORD)
            server.sendmail(MY_EMAIL, [email], msg.as_string())

        print("Reset email sent successfully")
    except Exception as e:
        print(f"Failed to send reset email. Error: {str(e)}")



@admin_api.route("/admin/<token>", methods=['GET', 'POST'])
def user_link_forgot_password(token):
    form = ChangePasswordForm()
    try:
        email = s.loads(token, salt='password-reset', max_age=1800)  # 30 minutes (1800 seconds)
        user = AdminUser.query.filter_by(email=email).first()

        if user:
            if form.validate_on_submit():
                user.password = pbkdf2_sha256.hash(form.new_password.data)
                db.session.commit()

                # Log successful password reset via token
                now = get_manila_now()
                log_activity(AdminActivityLogs, login_id=user.login_id,
                            logs_description=f"Password reset via token on {now.strftime('%Y-%m-%d %H:%M:%S')}")
                return ('<h1 style="font-family: Arial, sans-serif; font-size: 24px; color: #333; text-align: center; '
                        'margin-top: 50px;">Password reset successfully!</h1>')
            else:
                return render_template("reset_password.html", form=form, token=token) # Pass token to the template
        else:
            return jsonify(error={"message": "Invalid or expired token."}), 400 # 400 Bad request


    except SignatureExpired:
        return '<h1 style="font-family: Arial, sans-serif; font-size: 24px; color: #333; text-align: center; margin-top: 50px;">Token has expired.</h1>', 410  # 410 Gone
    except Exception as e:
        return jsonify(error={"message": f"An error occurred: {str(e)}"}), 500


@admin_api.post("/admin/logout")
def admin_logout():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"message": "Not Authorized", "details": "Invalid API Key"}), 403

        email = request.form.get("email")
        query_data = AdminUser.query.filter_by(email=email).first()

        if not query_data:
            return jsonify(error={"message": "Email not found."}), 404

        log_activity(AdminActivityLogs, login_id=query_data.login_id, logs_description="Logout successful")
        return jsonify(success={"message": "Successfully logged out."}), 200

    except Exception as e:
        return jsonify(error={"message": f"Failed to logout. Error: {str(e)}"}), 500


@admin_api.delete("/admin/delete_all")
def admin_delete_all():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(error={"Not Authorized": "Invalid API Key"}), 403

        admin_users = AdminUser.query.all()
        if not admin_users:
            return jsonify(message="No admin accounts found."), 404

        for admin in admin_users:
            log_activity(AdminActivityLogs, login_id=admin.login_id,
                         logs_description="Admin account deleted via mass deletion.")
            db.session.delete(admin)

        db.session.commit()
        return jsonify(success={"message": "All admin accounts deleted successfully."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify(error={"message": f"Failed to delete admin accounts. Error: {str(e)}"}), 500

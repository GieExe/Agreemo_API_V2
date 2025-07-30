from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from passlib.hash import pbkdf2_sha256
from itsdangerous import URLSafeTimedSerializer
from db import db
import smtplib
from flask import Blueprint, request, jsonify
import os
from models import Users, AdminUser
import random


verification_code_api = Blueprint("verification_code_api", __name__)

API_KEY = os.environ.get("API_KEY")

MY_EMAIL = os.environ.get('EMAIL')
MY_PASSWORD = os.environ.get("PASSWORD")
BASE_URL = os.environ.get("BASE_URL")

s = URLSafeTimedSerializer("Thisisasecret!")


def send_reset_email(email, verification_code, name):
    subject = 'Verification COde'
    body = f"""
        <html>
        <head>
            <style>
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
                <p>Here is your verification code: {verification_code}</p>

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

        print("Verification code sent successfully")
    except Exception as e:
        print(f"Failed to send verification code. Error: {str(e)}")


@verification_code_api.post("/send-verification-code")
def verification_forgot_pass():
    try:
        # Check API key for authorization
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct API key."}
            ), 403

        email = request.form.get("email")

        if not email:
            return jsonify(error={"message": "Email is required."}), 400

        existing_email = Users.query.filter_by(email=email).first()

        if not existing_email:
            return jsonify(error={"message": "Email not found"}), 404

        verification_code = str(random.randint(100000, 999999))

        # 🔹 Encrypt the code (valid for 3 minutes)
        signed_code = s.dumps(verification_code, salt=existing_email.email)

        name = f"{existing_email.last_name} "

        send_reset_email(email, verification_code, name)

        return jsonify({"token": signed_code, "message": "Verification code sent to your email"}), 200

    except Exception as e:

        return jsonify(error={"message": f"Failed to send verification code. Error: {str(e)}"}), 500


@verification_code_api.post("/verify-code")
def verify_code():
    try:
        # Check API key for authorization
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct API key."}
            ), 403

        email = request.form.get("email")
        verification_code = request.form.get("verification_code")
        signed_code = request.form.get("token")

        stored_code = s.loads(signed_code, salt=email, max_age=180)

        if stored_code == verification_code:
            return jsonify({"message": "Verification successful"}), 200
        else:
            return jsonify({"message": "Invalid verification code"}), 400

    except Exception as e:
        return jsonify({"message": f"Invalid or expired verification code. Error {str(e)}"}), 400


@verification_code_api.post("/user-reset-password")
def reset_password():
    try:
        # Check API key for authorization
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct API key."}
            ), 403

        email = request.form.get("email")
        new_password = request.form.get("new_password")
        signed_code = request.form.get("token")  # Token from /verify-code

        # Validate token (expires after 3 minutes)
        try:
            stored_code = s.loads(signed_code, salt=email, max_age=180)
        except Exception as e:
            return jsonify({"message": f"Invalid or expired token. Error {str(e)}"}), 400

        user = Users.query.filter_by(email=email).first()

        if not user:
            return jsonify({"message": "User not found"}), 404

        user.password = pbkdf2_sha256.hash(new_password)
        db.session.commit()

        return jsonify(sucess={"message": "Successfully change password."}), 200

    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500


@verification_code_api.post("/verify-user/activate")
def verify_user_activate():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct API key."}
            ), 403

        admin_email = request.form.get("admin_email")
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password or not admin_email:
            return jsonify(error={"message": "Email, password, and admin_email are required."}), 400

        user = Users.query.filter_by(email=email).first()
        admin = AdminUser.query.filter_by(email=admin_email).first()

        if not admin:
            return jsonify(error={"message": "Invalid admin email."}), 401

        if not pbkdf2_sha256.verify(password, admin.password):
            return jsonify(error={"message": "Invalid password."}), 401

        if not user:
            return jsonify(error={"message": "User not found."}), 404

        return jsonify({"message": f"User {user.first_name} {user.last_name} successfully deactivated to activate"}), 200

    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500


@verification_code_api.post("/verify-user/deactivate")
def verify_user_deactivate():
    try:
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct API key."}
            ), 403

        admin_email = request.form.get("admin_email")
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password or not admin_email:
            return jsonify(error={"message": "Email, password, and admin_email are required."}), 400

        user = Users.query.filter_by(email=email).first()
        admin = AdminUser.query.filter_by(email=admin_email).first()

        if not admin:
            return jsonify(error={"message": "Invalid admin email."}), 401

        if not pbkdf2_sha256.verify(password, admin.password):
            return jsonify(error={"message": "Invalid password."}), 401

        if not user:
            return jsonify(error={"message": "User not found."}), 404

        return jsonify({"message": f"User {user.first_name} {user.last_name} successfully activated to deactivate"}), 200

    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500


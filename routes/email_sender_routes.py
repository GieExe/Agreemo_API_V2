import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Blueprint, request, jsonify
from itsdangerous import URLSafeTimedSerializer

from db import db
from models import Users, StoredEmail

email_sender_api = Blueprint("email_sender_api", __name__)

API_KEY = os.environ.get("API_KEY")

MY_EMAIL = os.environ.get('EMAIL')
MY_PASSWORD = os.environ.get("PASSWORD")
BASE_URL = os.environ.get("BASE_URL")
APK_LINK = os.environ.get("APK_LINK")

s = URLSafeTimedSerializer('Thisisasecret!')


def send_email(email):
    subject = 'AGREEMO APK LINK'
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
            <p>Click the following link to get apk installer:  <a href="{APK_LINK}">AGREEMO APK</a></p>

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

        print("Apk email  successfully")
    except Exception as e:
        print(f"Failed to send apk link to email. Error: {str(e)}")


@email_sender_api.post("/apk-link-sender")
def email_sender():
    try:
        # Check API key for authorization
        api_key_header = request.headers.get("x-api-key")
        if api_key_header != API_KEY:
            return jsonify(
                error={"Not Authorized": "Sorry, that's not allowed. Make sure you have the correct API key."}
            ), 403

        # Extract and process emails from request
        emails = request.form.get("email", "").split(",")  # Split by comma
        emails = [email.strip() for email in emails if email.strip()]  # Remove spaces and empty entries
        results = []
        new_emails = []

        for email in emails:
            # Check if email is already stored
            if StoredEmail.query.filter_by(email=email).first():
                results.append({"email": email, "status": "already exists"})
            else:
                # Add new email to database
                new_email = StoredEmail(email=email)
                db.session.add(new_email)
                new_emails.append(email)  # Store only new emails for sending
                results.append({"email": email, "status": "added"})

        # Commit new emails to the database after processing all emails
        if new_emails:
            db.session.commit()

            # Send emails only to new addresses
            for email in new_emails:
                try:
                    send_email(email)  # APK link is sent inside this function
                    results.append({
                        "email": email,
                        "status": "success",
                        "message": "Agreemo APK link sent to your email."
                    })
                except Exception as e:
                    results.append({
                        "email": email,
                        "status": "failed",
                        "message": f"Failed to send email. Error: {str(e)}"
                    })

        return jsonify(results=results), 200

    except Exception as e:
        db.session.rollback()  # Rollback only if a database error occurs
        return jsonify(error={"message": f"Failed to send APK links. Error: {str(e)}"}), 500

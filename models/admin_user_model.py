#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\admin_user_model.py
from db import db
from datetime import datetime, timedelta
# Import related model
from models.activity_logs.admin_activity_logs_model import AdminActivityLogs # Assuming path

class AdminUser(db.Model):
    """Represents an administrator user with separate login credentials."""
    __tablename__ = "admin"

    login_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    consecutive_failed_login = db.Column(db.Integer, nullable=True, default=0)
    failed_timer = db.Column(db.DateTime, nullable=True)
    is_disabled = db.Column(db.Boolean, default=False)

    # --- Relationships ---
    # If AdminUser deleted, delete their logs
    admin_activity_logs = db.relationship(
        "AdminActivityLogs",
        back_populates="admin",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )

    def __repr__(self):
        return f"<AdminUser(id={self.login_id}, email='{self.email}', name='{self.name}')>"


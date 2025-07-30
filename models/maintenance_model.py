#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\maintenance_model.py
from db import db

class Maintenance(db.Model):
    """Represents a maintenance task record."""
    __tablename__ = "maintenance"

    maintenance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If a User is deleted, delete their Maintenance records
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String, nullable=False)
    date_completed = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    description = db.Column(db.String, nullable=True)
    name = db.Column(db.String, nullable=True) # Consider if this should be derived from user_id

    # --- Relationships ---
    # If Maintenance record is deleted, delete its logs
    maintenance_activity_logs = db.relationship(
        "MaintenanceActivityLogs",
        back_populates="maintenance",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )
    # Link back to the User who performed/logged the maintenance
    users = db.relationship("Users", back_populates="maintenance", lazy=True)

    def __repr__(self):
        return f"<Maintenance(id={self.maintenance_id}, title='{self.title}', user_id={self.user_id})>"


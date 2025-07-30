#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\hardware_current_status_model.py
from db import db

class HardwareCurrentStatus(db.Model):
    """Stores the last known status of a hardware component."""
    __tablename__ = "hardware_current_status"

    status_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If HardwareComponent deleted, delete its status record
    # Assuming component_id is unique here for One-to-One with HardwareComponents
    component_id = db.Column(db.Integer, db.ForeignKey('hardware_components.component_id', ondelete='CASCADE'), unique=True, nullable=False)
    isActive = db.Column(db.Boolean, nullable=False, default=False)
    # If Greenhouse deleted, delete this status record
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id', ondelete='CASCADE'), nullable=False)
    lastChecked = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp()) # Auto update timestamp
    statusNote = db.Column(db.String(200), nullable=True)

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="hardware_current_status", lazy=True)
    hardware_components = db.relationship("HardwareComponents", back_populates="hardware_current_status", lazy=True)
    # No child tables needing cascade from HardwareCurrentStatus

    def __repr__(self):
         return f"<HardwareCurrentStatus(id={self.status_id}, comp_id={self.component_id}, gh={self.greenhouse_id}, active={self.isActive})>"


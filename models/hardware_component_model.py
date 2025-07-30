#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\hardware_component_model.py
from db import db



class HardwareComponents(db.Model):
    """Represents a physical hardware component installed."""
    __tablename__ = "hardware_components"

    component_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If User deleted, delete their components
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False)
    # If Greenhouse deleted, delete its components
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id', ondelete='CASCADE'), nullable=False)
    componentName = db.Column(db.String(200), nullable=True)
    date_of_installation = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp()) # Use default
    manufacturer = db.Column(db.String(200), nullable=True)
    model_number = db.Column(db.String(200), nullable=True)
    serial_number = db.Column(db.String(200), nullable=True)

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="hardware_components", lazy=True)
    users = db.relationship("Users", back_populates="hardware_components", lazy=True)

    # If HardwareComponent deleted, delete related records:
    # Assuming one current status per component (One-to-One)
    hardware_current_status = db.relationship(
        "HardwareCurrentStatus",
        back_populates="hardware_components",
        lazy=True,
        cascade="all, delete-orphan", # Added cascade
        uselist=False # Specify One-to-One
    )
    hardware_status_activity_logs = db.relationship(
        "HardwareStatusActivityLogs",
        back_populates="hardware_components",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )
    hardware_components_activity_logs = db.relationship(
        "HardwareComponentActivityLogs",
        back_populates="hardware_components",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )

    def __repr__(self):
        return f"<HardwareComponent(id={self.component_id}, name='{self.componentName}', gh={self.greenhouse_id})>"


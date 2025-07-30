#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\greenhouses_model.py
from db import db


class Greenhouse(db.Model):
    """Represents a greenhouse structure."""
    __tablename__ = 'greenhouses'

    greenhouse_id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    # If User deleted, delete their Greenhouses
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String, nullable=False)
    location = db.Column(db.String, nullable=True)
    size = db.Column(db.Float, nullable=True)
    climate_type = db.Column(db.String, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    status = db.Column(db.String, nullable=False) # e.g., 'Active', 'Inactive'

    # --- Relationships ---
    users = db.relationship("Users", back_populates="greenhouses", lazy=True)

    # If Greenhouse deleted, delete all related records:
    analytics = db.relationship("Analytics", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    greenhouse_activity_logs = db.relationship("GreenHouseActivityLogs", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    harvests = db.relationship("Harvest", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    nutrient_controllers = db.relationship("NutrientController", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    plant_growth = db.relationship("PlantGrowth", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    reason_for_rejection = db.relationship("ReasonForRejection", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    planted_crops = db.relationship("PlantedCrops", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    # One-to-one relationship, cascade delete
    inventory_container = db.relationship("InventoryContainer", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan", uselist=False)
    inventory = db.relationship("Inventory", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    # Assuming InventoryItem model exists and relationship is correct
    inventory_items = db.relationship("InventoryItem", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    hardware_status_activity_logs = db.relationship("HardwareStatusActivityLogs", back_populates="greenhouses", foreign_keys="HardwareStatusActivityLogs.greenhouse_id", lazy=True, cascade="all, delete-orphan")
    hardware_current_status = db.relationship("HardwareCurrentStatus", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    hardware_components = db.relationship("HardwareComponents", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")
    nutrient_controller_activity_logs = db.relationship("NutrientControllerActivityLogs", back_populates="greenhouses", lazy=True, cascade="all, delete-orphan")

    # --- Constraints ---
    __table_args__ = (
        db.CheckConstraint(status.in_(['Active', 'Inactive']), name='valid_status'),
    )

    def __repr__(self):
        return f"<Greenhouse(id={self.greenhouse_id}, name='{self.name}', user_id={self.user_id})>"


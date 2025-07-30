#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\users_model.py
from db import db



class Users(db.Model):
    """Represents a regular user of the system."""
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String, nullable=False)
    last_name = db.Column(db.String, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    phone_number = db.Column(db.String, unique=True, nullable=True)
    address = db.Column(db.String, nullable=True)
    isAdmin = db.Column(db.Boolean, nullable=False, default=False)
    isActive = db.Column(db.Boolean, nullable=False, default=False)
    password = db.Column(db.String(200), nullable=False)
    consecutive_failed_login = db.Column(db.Integer, nullable=True, default=0)
    failed_timer = db.Column(db.DateTime, nullable=True)
    isNewUser = db.Column(db.Boolean, nullable=False, default=True)

    # --- Relationships ---
    # If a User is deleted, delete all associated records:
    greenhouses = db.relationship("Greenhouse", back_populates="users", lazy=True, cascade="all, delete-orphan")
    user_activity_logs = db.relationship("UserActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    rejection_activity_logs = db.relationship("RejectionActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    maintenance_activity_logs = db.relationship("MaintenanceActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    greenhouse_activity_logs = db.relationship("GreenHouseActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    harvest_activity_logs = db.relationship("HarvestActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    maintenance = db.relationship("Maintenance", back_populates="users", lazy=True, cascade="all, delete-orphan")
    hardware_components = db.relationship("HardwareComponents", back_populates="users", lazy=True, cascade="all, delete-orphan")
    harvests = db.relationship("Harvest", back_populates="users", lazy=True, cascade="all, delete-orphan")
    hardware_components_activity_logs = db.relationship("HardwareComponentActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    planted_crop_activity_logs = db.relationship("PlantedCropActivityLogs", back_populates="users", lazy=True, cascade="all, delete-orphan")
    sales = db.relationship("Sale", back_populates="users", lazy=True, cascade="all, delete-orphan")
    # Assuming these relationships are correct and models exist:
    inventory_item_logs = db.relationship("InventoryItemLog", back_populates="users", lazy=True, cascade="all, delete-orphan")
    inventory_items = db.relationship("InventoryItem", back_populates="users", lazy=True, cascade="all, delete-orphan")
    inventory_logs = db.relationship("InventoryLog", back_populates="users", lazy=True, cascade="all, delete-orphan")
    inventory_container_logs = db.relationship("InventoryContainerLog", back_populates="users", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.user_id}, email='{self.email}', name='{self.first_name} {self.last_name}')>"


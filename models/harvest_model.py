# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\harvest_model.py
from db import db
from sqlalchemy import func # Import func
from datetime import datetime # Import datetime
import pytz # Import pytz for timezone

# Define the timezone
try:
    PH_TZ = pytz.timezone('Asia/Manila')
except Exception:
    PH_TZ = pytz.timezone('Asia/Manila') # Fallback

class Harvest(db.Model):
    """
    Represents a harvest record in the database.
    Includes details about the harvested crop, yield, pricing, and status.
    """
    __tablename__ = 'harvests'

    harvest_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Consider ondelete='SET NULL' if user deletion shouldn't delete harvests
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False)
    # Consider ondelete='SET NULL' or 'RESTRICT' if greenhouse deletion shouldn't delete harvests
    greenhouse_id = db.Column(db.Integer, db.ForeignKey("greenhouses.greenhouse_id", ondelete='CASCADE'), nullable=False)
    # Consider ondelete='SET NULL' or 'RESTRICT' if planted crop deletion shouldn't delete harvests
    plant_id = db.Column(db.Integer, db.ForeignKey("planted_crops.plant_id", ondelete='CASCADE'), nullable=False) # Correct FK link
    plant_name = db.Column(db.String, nullable=False) # Store plant name at time of harvest
    name = db.Column(db.String, nullable=False) # Name of the harvest batch/event itself
    plant_type = db.Column(db.String, nullable=False)
    total_yield = db.Column(db.Integer, nullable=False)
    accepted = db.Column(db.Integer, nullable=False) # Quantity of accepted yield
    total_rejected = db.Column(db.Integer, nullable=False) # Quantity of rejected yield
    harvest_date = db.Column(db.Date, server_default=func.current_date()) # Date of harvest
    price = db.Column(db.Float, nullable=False) # Price per unit of accepted yield
    notes = db.Column(db.String) # Optional notes about the harvest
    total_price = db.Column(db.Float, nullable=False) # Calculated total price (accepted * price)

    # Status of the harvested items (e.g., Not Sold, Sold, Processing, Spoiled)
    status = db.Column(db.String(50), nullable=False, server_default='Not Sold', index=True) # Added index

    # Timestamp for the last update to the record. Automatically updates.
    last_updated = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(pytz.utc), onupdate=lambda: datetime.now(pytz.utc)) # Store UTC

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="harvests", lazy=True)
    harvest_activity_logs = db.relationship("HarvestActivityLogs", back_populates="harvests", lazy=True, cascade="all, delete-orphan")
    users = db.relationship("Users", back_populates="harvests", lazy=True) # Changed from 'users' to 'user'
    planted_crops = db.relationship("PlantedCrops", back_populates="harvests", lazy=True)

    # --- NEW RELATIONSHIP TO SALES ---
    # Links this harvest to potentially multiple sale records (e.g., if sold in parts, though current logic sells all at once)
    # If Harvest is deleted, associated Sales should likely be kept with harvest_id set to NULL.
    # cascade="all, delete" would delete sales if harvest is deleted - decide based on business logic.
    # Using default (no cascade, foreign key handles SET NULL based on Sale model)
    sales = db.relationship("Sale", back_populates="harvest", lazy=True)
    # --- END NEW RELATIONSHIP ---

    def __repr__(self):
        """
        Provides a string representation of the Harvest object, useful for debugging.
        """
        return (f"<Harvest(id={self.harvest_id}, name='{self.name}', plant='{self.plant_name}', "
                f"status='{self.status}', last_updated='{self.last_updated.isoformat() if self.last_updated else None}')>")

    # Helper to convert to dictionary
    def to_dict(self):
        return {
            "harvest_id": self.harvest_id,
            "user_id": self.user_id,
            "greenhouse_id": self.greenhouse_id,
            "plant_id": self.plant_id,
            "plant_name": self.plant_name,
            "name": self.name,
            "plant_type": self.plant_type,
            "total_yield": self.total_yield,
            "accepted": self.accepted,
            "total_rejected": self.total_rejected,
            "harvest_date": self.harvest_date.isoformat() if self.harvest_date else None,
            "price": float(self.price) if self.price is not None else None,
            "notes": self.notes,
            "total_price": float(self.total_price) if self.total_price is not None else None,
            "status": self.status,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }

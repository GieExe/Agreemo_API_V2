#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\inventory_model.py
from db import db
import pytz
from datetime import datetime

# Define timezone if needed elsewhere, though default=datetime.now(pytz.utc) uses UTC
# PH_TZ = pytz.timezone('Asia/Manila')

class InventoryContainer(db.Model):
    """
    Represents the current levels of consumable inventory items (like pH solutions)
    within a specific greenhouse.
    """
    __tablename__ = 'inventory_container'

    inventory_container_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Ensure ON DELETE behavior is appropriate for greenhouse_id FK if greenhouse is deleted
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id', ondelete='CASCADE'), nullable=False, unique=True) # Assuming one container per greenhouse

    # Current levels (e.g., in ml or units)
    ph_up = db.Column(db.Integer, nullable=False, default=0)
    ph_down = db.Column(db.Integer, nullable=False, default=0)
    solution_a = db.Column(db.Integer, nullable=False, default=0)
    solution_b = db.Column(db.Integer, nullable=False, default=0)

    # Critical level threshold for alerts
    critical_level = db.Column(db.Integer, nullable=False, default=0)

    # --- Relationships ---
    # Relationship back to Greenhouse (One-to-One)
    # Use uselist=False for one-to-one from this side
    greenhouses = db.relationship("Greenhouse", back_populates="inventory_container", lazy=True, uselist=False)

    # Relationship to Inventory items (One-to-Many: One container can be linked from multiple inventory additions)
    # When a container is deleted, we likely want to UNLINK associated inventory items,
    # NOT delete them. Setting inventory_container_id to NULL is handled by the nullable=True
    # in the Inventory model's foreign key definition. No cascade needed here for deletion.
    inventory = db.relationship("Inventory", back_populates="inventory_container", lazy=True) # Use dynamic if potentially many inventory items per container

    # Relationship to Container Logs (One-to-Many)
    # When a container is deleted, its logs should also be deleted.
    inventory_container_logs = db.relationship(
        "InventoryContainerLog",
        back_populates="inventory_container",
        lazy=True,
        cascade="all, delete-orphan" # Delete logs when container is deleted
    )


    def __repr__(self):
        return f"<InventoryContainer(id={self.inventory_container_id}, gh_id={self.greenhouse_id}, ph_up={self.ph_up}, ph_down={self.ph_down}, sol_a={self.solution_a}, sol_b={self.solution_b})>"

class Inventory(db.Model):
    """
    Represents a specific inventory item record, often corresponding to a purchase
    or addition of stock (e.g., a bottle of pH Up).
    """
    __tablename__ = "inventory"

    inventory_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Foreign key to the container this item contributes to (if applicable)
    # nullable=True allows items not linked to a container, or unlinking when container is deleted.
    inventory_container_id = db.Column(db.Integer, db.ForeignKey('inventory_container.inventory_container_id', ondelete='SET NULL'), nullable=True)
    # Foreign key to the greenhouse this inventory belongs to
    # Ensure ON DELETE behavior is appropriate if greenhouse is deleted
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id', ondelete='CASCADE'), nullable=False)

    item_name = db.Column(db.String, nullable=False) # e.g., "Brand X pH Up 1L"
    user_name = db.Column(db.String, nullable=False) # Name of user who added this record
    type = db.Column(db.String(200), nullable=False) # e.g., "ph_up", "seeds", "fertilizer"
    quantity = db.Column(db.Integer, nullable=False, default=1) # Quantity of this specific item/package added
    total_price = db.Column(db.Float, nullable=False, default=0.0) # Total cost for this quantity
    max_total_ml = db.Column(db.Float, nullable=True, default=0.0) # Optional: Size of package (e.g., 1000 for 1L bottle)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(pytz.utc)) # Use lambda for default
    price = db.Column(db.Float, nullable=False, default=0.0) # Price per unit/package

    # --- Relationships ---
    # Relationship back to the container (Many-to-One)
    inventory_container = db.relationship("InventoryContainer", back_populates="inventory", lazy=True)

    # Relationship back to the greenhouse (Many-to-One)
    greenhouses = db.relationship("Greenhouse", back_populates="inventory", lazy=True)

    # Relationship to Inventory Logs (One-to-Many)
    # When an inventory item record is deleted, its specific logs should also be deleted.
    inventory_logs = db.relationship(
        "InventoryLog",
        back_populates="inventory",
        lazy=True,
        cascade="all, delete-orphan" # Delete logs when inventory item is deleted
    )

    def __repr__(self):
         return f"<Inventory(id={self.inventory_id}, item='{self.item_name}', gh_id={self.greenhouse_id}, qty={self.quantity})>"


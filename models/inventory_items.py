# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\inventory_items.py
# --- VERSION WITH CASCADE DELETE ADDED TO LOGS RELATIONSHIP ---

from db import db
import pytz
from datetime import datetime


class InventoryItem(db.Model):
    __tablename__ = 'inventory_items'

    inventory_item_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Foreign key to the user who owns/added this item initially (or is responsible)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id'), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    unit = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    price = db.Column(db.Float, nullable=False, default=0.0)
    total_price = db.Column(db.Float, nullable=False, default=0.0) # Should be updated when count/price changes
    date_received = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(pytz.utc)) # Use lambda for default

    # --- Relationships ---

    # Relationship to logs: If an item is deleted, delete its logs too.
    inventory_item_logs = db.relationship(
        "InventoryItemLog",
        back_populates="inventory_items",
        lazy=True,
        cascade="all, delete-orphan" # MODIFIED: Added cascade deletion
    )

    # Relationship to Greenhouse (Many Items to One Greenhouse)
    greenhouses = db.relationship(
        "Greenhouse",
        back_populates="inventory_items",
        lazy=True
    )

    # Relationship to User (Many Items added by One User)
    users = db.relationship(
        "Users",
        back_populates="inventory_items",
        lazy=True
    )

    def __repr__(self):
        return f"<InventoryItem(id={self.inventory_item_id}, name='{self.item_name}', count={self.item_count}, unit='{self.unit}')>"
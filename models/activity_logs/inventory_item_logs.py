# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\inventory_item_logs.py
from datetime import datetime

import pytz

from db import db


class InventoryItemLog(db.Model):
    __tablename__ = 'inventory_item_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_items.inventory_item_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.now(pytz.utc))
    activity_type = db.Column(db.String(50), nullable=False)  # e.g., "create", "update", "delete"
    description = db.Column(db.String(500), nullable=True)

    # Relationships
    inventory_items = db.relationship("InventoryItem", back_populates="inventory_item_logs", lazy=True)
    users = db.relationship("Users", back_populates="inventory_item_logs", lazy=True) # Direct relationship

    def __repr__(self):
        return f"<InventoryItemLog(item_id={self.inventory_item_id}, activity='{self.activity_type}')>"
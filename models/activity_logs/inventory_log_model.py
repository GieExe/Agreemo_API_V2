#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\inventory_log_model.py
from datetime import datetime

import pytz

from db import db



class InventoryLog(db.Model):
    __tablename__ = 'inventory_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # RECOMMENDED CHANGE: Rename column and FK reference to be clear
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.inventory_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False) # Track WHICH user made the change
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(pytz.utc)) # Use lambda for default
    change_type = db.Column(db.String(50), nullable=False)  # e.g., "create", "update", "delete"
    description = db.Column(db.String(255), nullable=True)

    # Relationships (assuming Inventory has 'inventory_logs' and Users has 'inventory_logs')
    inventory = db.relationship("Inventory", back_populates="inventory_logs", lazy=True)
    users = db.relationship("Users", back_populates="inventory_logs", lazy=True)

    def __repr__(self):
        return f"<InventoryLog(log_id={self.log_id}, inventory_id={self.inventory_id}, user_id={self.user_id}, change_type='{self.change_type}')>"
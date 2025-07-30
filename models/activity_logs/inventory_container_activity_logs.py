# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\inventory_container_activity_logs.py
from datetime import datetime
import pytz
from db import db

class InventoryContainerLog(db.Model):
    __tablename__ = 'inventory_container_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inventory_container_id = db.Column(db.Integer, db.ForeignKey('inventory_container.inventory_container_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False) # *** ADD THIS LINE ***
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(pytz.utc)) # Use lambda
    change_type = db.Column(db.String(50), nullable=False)  # e.g., "update", "delete"
    item = db.Column(db.String(50), nullable=True)  # Item updated or N/A for delete
    old_quantity = db.Column(db.Integer, nullable=True)
    new_quantity = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(255), nullable=True)

    # *** ADD relationship in Users model: ***
    # container_logs = db.relationship("InventoryContainerLog", back_populates="user", lazy=True)

    # *** Update existing relationships ***
    inventory_container = db.relationship("InventoryContainer", back_populates="inventory_container_logs", lazy=True)
    users = db.relationship("Users", back_populates="inventory_container_logs", lazy=True) # *** ADD THIS LINE ***


    def __repr__(self):
        # ... (repr can be updated)
        return f"<InventoryContainerLog(log_id={self.log_id}, user_id={self.user_id}, change_type='{self.change_type}', item='{self.item}')>"
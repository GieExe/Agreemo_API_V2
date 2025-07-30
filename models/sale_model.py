# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\sale_model.py
from db import db
import pytz
from datetime import datetime
from sqlalchemy import CheckConstraint # Import CheckConstraint

# Define the timezone (assuming PH_TZ is defined elsewhere or here)
try:
    # Attempt to get PH_TZ from Flask app context if available
    # This might not work directly in the model definition time
    # from flask import current_app
    # PH_TZ = current_app.config.get('PH_TZ', pytz.timezone('Asia/Manila'))
    # Safer approach: Define it directly or ensure it's globally accessible
    PH_TZ = pytz.timezone('Asia/Manila')
except Exception:
    PH_TZ = pytz.timezone('Asia/Manila') # Fallback

class Sale(db.Model):
    """
    Represents a sales transaction record, linked to either a Harvest
    or a ReasonForRejection record.
    """
    __tablename__ = 'sales'

    sale_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If User deleted, set user_id to NULL? Or prevent deletion?
    # Current: Cascade delete might be too aggressive if user deletion shouldn't delete sales history.
    # Consider setting user_id to nullable and using ondelete='SET NULL' if user deletion is allowed.
    # For now, keeping original cascade behavior but adding a comment.
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id", ondelete='CASCADE'), nullable=False) # User who recorded the sale

    # --- Link to the source of the sale ---
    # A sale originates from EITHER a Harvest OR a Rejection, not both.
    # If the source Harvest/Rejection is deleted, set these FKs to NULL (or delete Sale if required).
    # Using ondelete='SET NULL' allows Sale history to remain even if source is deleted.
    harvest_id = db.Column(db.Integer, db.ForeignKey("harvests.harvest_id", ondelete='SET NULL'), nullable=True, index=True)
    rejection_id = db.Column(db.Integer, db.ForeignKey("reason_for_rejection.rejection_id", ondelete='SET NULL'), nullable=True, index=True)
    # --- End source link ---

    plant_name = db.Column(db.String, nullable=False) # Name of the plant at time of sale (copied from source)
    name = db.Column(db.String, nullable=False) # Name associated with the user who made the sale (copied from user)

    # Pricing details
    originalPrice = db.Column(db.Float, nullable=True) # Original price from Harvest/Rejection (copied for history)
    currentPrice = db.Column(db.Float, nullable=False) # Price actually sold at (from request)
    quantity = db.Column(db.Float, nullable=False) # Quantity sold (from request, validated against source)
    total_price = db.Column(db.Float, nullable=False) # Calculated total for this sale (currentPrice * quantity)

    cropDescription = db.Column(db.String(200), nullable=True) # Optional description for the sale
    salesDate = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(pytz.utc)) # Use lambda, store UTC

    # --- Relationships ---
    # If Sale deleted, delete its logs
    sale_logs = db.relationship(
        "SaleLog",
        back_populates="sales",
        lazy=True,
        cascade="all, delete-orphan" # Keep cascade
    )
    # Link back to the User who recorded the sale
    users = db.relationship("Users", back_populates="sales", lazy=True)

    # Link back to the source Harvest (if applicable)
    harvest = db.relationship("Harvest", back_populates="sales", lazy=True)

    # Link back to the source Rejection (if applicable)
    reason_for_rejection = db.relationship("ReasonForRejection", back_populates="sales", lazy=True)

    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            '(harvest_id IS NOT NULL AND rejection_id IS NULL) OR (harvest_id IS NULL AND rejection_id IS NOT NULL)',
            name='chk_sale_source_exclusive'
        ),
        # Add other constraints if needed
    )

    def __repr__(self):
        source_id = f"H:{self.harvest_id}" if self.harvest_id else f"R:{self.rejection_id}"
        return (f"<Sale(id={self.sale_id}, source={source_id}, plant='{self.plant_name}', "
                f"qty={self.quantity}, total={self.total_price}, date={self.salesDate})>")

    # Helper to convert to dictionary, useful for JSON responses
    def to_dict(self):
        return {
            "sale_id": self.sale_id,
            "user_id": self.user_id,
            "user_name": self.name, # Name of user who made sale
            "harvest_id": self.harvest_id,
            "rejection_id": self.rejection_id,
            "plant_name": self.plant_name,
            "originalPrice": float(self.originalPrice) if self.originalPrice is not None else None,
            "currentPrice": float(self.currentPrice) if self.currentPrice is not None else None,
            "quantity": float(self.quantity) if self.quantity is not None else None,
            "total_price": float(self.total_price) if self.total_price is not None else None,
            "cropDescription": self.cropDescription,
            "salesDate": self.salesDate.isoformat() if self.salesDate else None # Use ISO format for consistency
        }

# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\reason_for_rejection_model.py
from db import db
from sqlalchemy import func, ForeignKey

class ReasonForRejection(db.Model):
    """
    Represents a record detailing rejected produce, including the reason,
    quantity, pricing adjustments, and status.
    """
    __tablename__ = "reason_for_rejection"

    rejection_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Consider ondelete behavior based on requirements (CASCADE, SET NULL, RESTRICT)
    greenhouse_id = db.Column(db.Integer, db.ForeignKey("greenhouses.greenhouse_id", ondelete='CASCADE'), nullable=False)
    plant_id = db.Column(db.Integer, db.ForeignKey("planted_crops.plant_id", ondelete='CASCADE'), nullable=False)
    plant_name = db.Column(db.String, nullable=True) # Name of the plant
    type = db.Column(db.String, nullable=True) # e.g., 'too_small', 'damaged', 'diseased'
    quantity = db.Column(db.Integer, nullable=False) # Quantity rejected
    rejection_date = db.Column(db.Date, server_default=func.current_date())
    comments = db.Column(db.String, nullable=True)
    price = db.Column(db.Float, nullable=False) # Potential salvage value price per unit?
    deduction_rate = db.Column(db.Float, nullable=False) # Percentage deduction if applicable
    total_price = db.Column(db.Float, nullable=False) # Calculated potential value after deductions
    # Status: Not Sold, Sold, Disposed, Processing
    status = db.Column(db.String(50), nullable=False, server_default='Not Sold', index=True) # Added index

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="reason_for_rejection", lazy=True) # Renamed from greenhouses
    rejection_activity_logs = db.relationship(
        "RejectionActivityLogs",
        back_populates="reason_for_rejection",
        lazy=True,
        cascade="all, delete-orphan" # Keep cascade
    )
    planted_crops = db.relationship("PlantedCrops", back_populates="reason_for_rejection", lazy=True)

    # --- NEW RELATIONSHIP TO SALES ---
    # Links this rejection record to potentially multiple sale records (if sold)
    # If Rejection is deleted, associated Sales should likely be kept with rejection_id set to NULL.
    sales = db.relationship("Sale", back_populates="reason_for_rejection", lazy=True)
    # --- END NEW RELATIONSHIP ---

    def __repr__(self):
        return (f"<ReasonForRejection(id={self.rejection_id}, plant='{self.plant_name}', "
                f"type='{self.type}', qty={self.quantity}, status='{self.status}')>")

    # Helper to convert to dictionary
    def to_dict(self):
        return {
            "rejection_id": self.rejection_id,
            "greenhouse_id": self.greenhouse_id,
            "plant_id": self.plant_id,
            "plant_name": self.plant_name,
            "type": self.type,
            "quantity": self.quantity,
            "rejection_date": self.rejection_date.isoformat() if self.rejection_date else None,
            "comments": self.comments,
            "price": float(self.price) if self.price is not None else None,
            "deduction_rate": float(self.deduction_rate) if self.deduction_rate is not None else None,
            "total_price": float(self.total_price) if self.total_price is not None else None,
            "status": self.status,
        }


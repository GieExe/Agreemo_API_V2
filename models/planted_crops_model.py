# C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\planted_crops_model.py
from sqlalchemy import Column, Integer, Date, ForeignKey, CheckConstraint, Numeric, String
from db import db


class PlantedCrops(db.Model):
    """Represents a batch of crops planted in a greenhouse."""
    __tablename__ = 'planted_crops'

    plant_id = Column(Integer, primary_key=True, autoincrement=True)
    # If Greenhouse deleted, delete these records
    greenhouse_id = Column(Integer, ForeignKey("greenhouses.greenhouse_id", ondelete='CASCADE'), nullable=False)
    planting_date = Column(Date, nullable=False)
    # Unique constraint ensures no two active crops have the same name? Reconsider if needed.
    plant_name = db.Column(db.String, nullable=True, unique=True)
    seedlings_daysOld = Column(Integer, nullable=False)
    name = db.Column(db.String, nullable=False) # Type/Variety name?
    greenhouse_daysOld = Column(Integer, nullable=False)
    count = Column(Integer, nullable=False) # Number of plants in this batch

    # Current readings (optional)
    tds_reading = Column(Numeric(10, 2), nullable=True)
    ph_reading = Column(Numeric(10, 2), nullable=True)

    # Status of the crop batch
    status = Column(String(50), nullable=False, default="not harvested") # e.g., "not harvested", "harvested", "failed"
    total_days_grown = Column(Integer, nullable=False)

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="planted_crops", lazy=True)

    # If PlantedCrops deleted, delete related records:
    planted_crop_activity_logs = db.relationship(
        "PlantedCropActivityLogs",
        back_populates="planted_crops",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )
    harvests = db.relationship(
        "Harvest",
        back_populates="planted_crops",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )
    nutrient_controllers = db.relationship(
        "NutrientController",
        back_populates="planted_crops",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )
    reason_for_rejection = db.relationship(
        "ReasonForRejection",
        back_populates="planted_crops",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )


    # --- Constraints ---
    __table_args__ = (
        CheckConstraint("count > 0", name="check_count_positive"),
        # Add other constraints as needed
    )

    def __repr__(self):
        return f"<PlantedCrops(id={self.plant_id}, name='{self.plant_name}', gh={self.greenhouse_id}, status='{self.status}')>"


#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\nutrient_controllers_model.py
from db import db
from sqlalchemy import ForeignKey



class NutrientController(db.Model):
    """Represents a record of nutrient/pH solution dispensing."""
    __tablename__ = 'nutrient_controllers'

    controller_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If Greenhouse deleted, delete these records
    greenhouse_id = db.Column(db.Integer, db.ForeignKey("greenhouses.greenhouse_id", ondelete='CASCADE'), nullable=False)
    # If PlantedCrop deleted, delete these records
    plant_id = db.Column(db.Integer, db.ForeignKey("planted_crops.plant_id", ondelete='CASCADE'), nullable=False)
    plant_name = db.Column(db.String, nullable=False) # Name at time of dispensing
    solution_type = db.Column(db.String, nullable=False) # e.g., 'pH Up', 'Nutrient A'
    dispensed_amount = db.Column(db.Float, nullable=False) # e.g., ml
    activated_by = db.Column(db.String, nullable=False) # e.g., 'System', 'User: Giebert'
    dispensed_time = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp()) # Use default

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="nutrient_controllers", lazy=True)
    planted_crops = db.relationship("PlantedCrops", back_populates="nutrient_controllers", lazy=True)
    # If this record deleted, delete its logs
    nutrient_controller_activity_logs = db.relationship(
        "NutrientControllerActivityLogs",
        back_populates="nutrient_controllers",
        lazy=True,
        cascade="all, delete-orphan" # Added cascade
    )

    # --- Constraints ---
    __table_args__ = (
        db.CheckConstraint(solution_type.in_(['pH Up', 'pH Down', 'Nutrient A', 'Nutrient B']),
                           name='valid_solution_type'),
    )

    def __repr__(self):
        return f"<NutrientController(id={self.controller_id}, gh={self.greenhouse_id}, plant={self.plant_id}, type='{self.solution_type}', amount={self.dispensed_amount})>"


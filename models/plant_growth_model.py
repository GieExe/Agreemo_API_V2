#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\plant_growth_model.py
from db import db


class PlantGrowth(db.Model):
    """Represents an observation of plant growth parameters."""
    __tablename__ = 'plant_growth'

    growth_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If Greenhouse deleted, delete these records
    greenhouse_id = db.Column(db.Integer, db.ForeignKey("greenhouses.greenhouse_id", ondelete='CASCADE'), nullable=False)
    plant_type = db.Column(db.String, nullable=False) # General type, not specific plant_id
    height = db.Column(db.Float, nullable=True) # Optional
    leaf_count = db.Column(db.Integer, nullable=True) # Optional
    growth_stage = db.Column(db.String, nullable=False)
    observed_date = db.Column(db.Date, server_default=db.func.current_date())
    remarks = db.Column(db.String, nullable=True)

    # --- Relationships ---
    greenhouses = db.relationship("Greenhouse", back_populates="plant_growth", lazy=True)
    # No child tables defined here needing cascade from PlantGrowth

    # --- Constraints ---
    __table_args__ = (
        db.CheckConstraint(growth_stage.in_(['Seedling', 'Vegetative', 'Mature', 'Harvest']),
                           name='valid_growth_stage'),
    )

    def __repr__(self):
        return f"<PlantGrowth(id={self.growth_id}, gh={self.greenhouse_id}, type='{self.plant_type}', stage='{self.growth_stage}')>"


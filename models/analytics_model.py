#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\analytics_model.py
from db import db
from sqlalchemy import ForeignKey
# Import related model
from models.greenhouses_model import Greenhouse # Assuming path

class Analytics(db.Model):
    """Represents calculated analytics data for a greenhouse over a period."""
    __tablename__ = 'analytics'

    analytics_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # If Greenhouse deleted, delete associated analytics
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id', ondelete='CASCADE'), nullable=False)
    period = db.Column(db.String, nullable=False) # e.g., 'Daily', 'Monthly'
    average_ph = db.Column(db.Float, nullable=True)
    average_temperature = db.Column(db.Float, nullable=True)
    yield_prediction = db.Column(db.Float, nullable=True)
    sensor_activations = db.Column(db.Integer, nullable=True)

    # --- Relationships ---
    greenhouses = db.relationship('Greenhouse', back_populates='analytics', lazy=True)
    # No child tables needing cascade from Analytics

    # --- Constraints ---
    __table_args__ = (
        db.CheckConstraint(period.in_(['Daily', 'Monthly', 'Yearly']), name='valid_period'),
    )

    def __repr__(self):
        return f"<Analytics(id={self.analytics_id}, gh={self.greenhouse_id}, period='{self.period}')>"


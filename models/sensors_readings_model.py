#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\sensors_readings_model.py
from db import db


class SensorReading(db.Model):
    """Represents a single reading from a sensor."""
    __tablename__ = 'sensor_readings'

    reading_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Consider adding ForeignKey to a Sensor/HardwareComponent table if applicable
    # component_id = db.Column(db.Integer, db.ForeignKey("hardware_components.component_id", ondelete='CASCADE'), nullable=True)
    # Consider adding ForeignKey to Greenhouse
    # greenhouse_id = db.Column(db.Integer, db.ForeignKey("greenhouses.greenhouse_id", ondelete='CASCADE'), nullable=True)
    reading_value = db.Column(db.Float, nullable=False)
    reading_time = db.Column(db.DateTime, server_default=db.func.current_timestamp())
    unit = db.Column(db.String, nullable=False) # e.g., '°C', 'pH', 'ppm'

    # Define relationships if ForeignKeys are added above
    # hardware_component = db.relationship(...)
    # greenhouse = db.relationship(...)

    def __repr__(self):
         return f"<SensorReading(id={self.reading_id}, value={self.reading_value}, unit='{self.unit}', time='{self.reading_time}')>"


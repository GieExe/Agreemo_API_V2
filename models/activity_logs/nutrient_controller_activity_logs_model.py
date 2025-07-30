#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\nutrient_controller_activity_logs_model.py
from db import db


class NutrientControllerActivityLogs(db.Model):
    __tablename__ = "nutrient_controller_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    controller_id = db.Column(db.Integer, db.ForeignKey('nutrient_controllers.controller_id'))
    logs_description = db.Column(db.String(200))
    logs_date = db.Column(db.DateTime, nullable=False)
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id'))  # ForeignKey to Greenhouse
    activated_by = db.Column(db.String(200), nullable=False)

    greenhouses = db.relationship("Greenhouse", back_populates="nutrient_controller_activity_logs", lazy=True)
    nutrient_controllers = db.relationship("NutrientController", back_populates="nutrient_controller_activity_logs", lazy=True)

#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\planted_crop_activity_logs_model.py
from db import db

class PlantedCropActivityLogs(db.Model):
    __tablename__ = "planted_crop_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    plant_id = db.Column(db.Integer, db.ForeignKey('planted_crops.plant_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    # Use the string representation of the class name:
    planted_crops = db.relationship("PlantedCrops", back_populates="planted_crop_activity_logs", lazy=True)
    users = db.relationship("Users", back_populates="planted_crop_activity_logs", lazy=True)
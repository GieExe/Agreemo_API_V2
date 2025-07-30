#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\hardware_components_activity_logs_model.py
from db import db


class HardwareComponentActivityLogs(db.Model):
    __tablename__ = "hardware_components_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    component_id = db.Column(db.Integer, db.ForeignKey('hardware_components.component_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    users = db.relationship("Users", back_populates="hardware_components_activity_logs", lazy=True)
    hardware_components = db.relationship("HardwareComponents", back_populates="hardware_components_activity_logs", lazy=True)

#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\maintenance_activity_logs_model.py
from db import db



class MaintenanceActivityLogs(db.Model):
    __tablename__ = "maintenance_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    maintenance_id = db.Column(db.Integer, db.ForeignKey('maintenance.maintenance_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(255), nullable=False)

    maintenance = db.relationship("Maintenance", back_populates="maintenance_activity_logs", lazy=True)
    users = db.relationship("Users", back_populates="maintenance_activity_logs", lazy=True)

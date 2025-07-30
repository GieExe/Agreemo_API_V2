#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\harvest_activity_logs_model.py
from db import db


class HarvestActivityLogs(db.Model):
    __tablename__ = "harvest_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    harvest_id = db.Column(db.Integer, db.ForeignKey('harvests.harvest_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    harvests = db.relationship("Harvest", back_populates="harvest_activity_logs", lazy=True)
    users = db.relationship("Users", back_populates="harvest_activity_logs", lazy=True)

#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\user_activity_logs_model.py
from db import db


class UserActivityLogs(db.Model):
    __tablename__ = "user_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    users = db.relationship("Users", back_populates="user_activity_logs", lazy=True)



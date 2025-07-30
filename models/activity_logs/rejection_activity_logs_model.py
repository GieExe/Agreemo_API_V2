#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\rejection_activity_logs_model.py
from db import db


class RejectionActivityLogs(db.Model):
    __tablename__ = "rejection_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    rejection_id = db.Column(db.Integer, db.ForeignKey('reason_for_rejection.rejection_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    reason_for_rejection = db.relationship("ReasonForRejection", back_populates="rejection_activity_logs", lazy=True)
    users = db.relationship("Users", back_populates="rejection_activity_logs", lazy=True)



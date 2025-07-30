from db import db


class AdminActivityLogs(db.Model):
    __tablename__ = "admin_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('admin.login_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    admin = db.relationship("AdminUser", back_populates="admin_activity_logs", lazy=True)



from db import db


class GreenHouseActivityLogs(db.Model):
    __tablename__ = "greenhouse_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id'))
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, nullable=False)

    greenhouses = db.relationship("Greenhouse", back_populates="greenhouse_activity_logs", lazy=True)
    users = db.relationship("Users", back_populates="greenhouse_activity_logs", lazy=True)
from db import db  # Import db from the models package
from sqlalchemy import text  # Import


class ControlActivityLogs(db.Model):
    __tablename__ = "control_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    logs_description = db.Column(db.String(255), nullable=False)
    log_date = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'), nullable=False)
    pump1 = db.Column(db.Boolean)
    pump2 = db.Column(db.Boolean)
    exhaust = db.Column(db.Boolean)
    automode = db.Column(db.Boolean)

    # Add a unique constraint
    __table_args__ = (
        db.UniqueConstraint('log_date', 'pump1', 'pump2', 'exhaust', 'automode', 'logs_description', name='uq_control_activity_logs'),
    )

    def __repr__(self):
        return f"<ControlActivityLog {self.log_id}: {self.logs_description}>"
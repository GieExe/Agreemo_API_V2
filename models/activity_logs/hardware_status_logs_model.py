from db import db


class HardwareStatusActivityLogs(db.Model):
    __tablename__ = "hardware_status_activity_logs"

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    logs_description = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Boolean, nullable=False, default=False)
    duration = db.Column(db.String(200))
    component_id = db.Column(db.Integer, db.ForeignKey('hardware_components.component_id'))  # ForeignKey to HardwareComponents
    greenhouse_id = db.Column(db.Integer, db.ForeignKey('greenhouses.greenhouse_id'))  # ForeignKey to Greenhouse

    # Relationship to HardwareComponents
    hardware_components = db.relationship("HardwareComponents",
                                          back_populates="hardware_status_activity_logs",
                                          lazy=True)

    # Relationship to Greenhouse
    greenhouses = db.relationship("Greenhouse",
                                  back_populates="hardware_status_activity_logs",
                                  lazy=True)

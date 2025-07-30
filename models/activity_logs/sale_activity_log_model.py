#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\activity_logs\sale_activity_log_model.py
from db import db
import pytz
from datetime import datetime


class SaleLog(db.Model):
    __tablename__ = 'sale_logs'

    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.sale_id'), nullable=False)  # Foreign key referencing Sale.id
    login_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)  # Foreign key to Users table - Removed for now
    log_message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False, default=datetime.now(pytz.utc))

    sales = db.relationship("Sale", back_populates="sale_logs")  # Relationship to Sale
    users = db.relationship("Users", backref="sale_logs")  # Relationship to Users - Removed for now

    def __repr__(self):
        return f"<SaleLog(log_id={self.log_id}, sale_id={self.sale_id}, log_message='{self.log_message}', timestamp={self.timestamp})>"
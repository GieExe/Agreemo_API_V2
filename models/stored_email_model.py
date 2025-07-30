#C:\Users\Giebert\PycharmProjects\agreemo_api_v2\models\stored_email_model.py
from db import db

class StoredEmail(db.Model):
    """Stores emails, perhaps for mailing lists or allowed users."""
    __tablename__ = 'stored_email'

    stored_email_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String, unique=True, nullable=False)
    # No relationships defined needing cascade

    def __repr__(self):
        return f"<StoredEmail(id={self.stored_email_id}, email='{self.email}')>"


from db import db
from datetime import datetime
import pytz


def log_activity(table_name, **kwargs):
    try:
        # Get current time in Philippines time zone
        ph_tz = pytz.timezone('Asia/Manila')
        manila_now = datetime.now(ph_tz)
        naive_manila_now = manila_now.replace(tzinfo=None)  # Convert to naive datetime
        
        new_activity_log = table_name(**kwargs, log_date=naive_manila_now)
        db.session.add(new_activity_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


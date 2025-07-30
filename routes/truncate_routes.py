from flask import Blueprint, request
from sqlalchemy import text
from db import db

truncate_api = Blueprint("truncate_api", __name__)


@truncate_api.route("/truncate-all/test", methods=["POST"])
def truncate_all_tables():
    try:
        code = request.form.get("code")
        if code != "CapstoneProjectAgreemo":
            return {"error": "Unauthorized access."}, 403

        # Detect database dialect
        dialect = db.engine.dialect.name

        if dialect == "postgresql":
            # Disable constraints for PostgreSQL
            db.session.execute(text("SET session_replication_role = 'replica';"))

        # Truncate all tables
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(text(f"DELETE FROM {table.name};"))  # Use DELETE for SQLite

        if dialect == "postgresql":
            # Enable constraints back for PostgreSQL
            db.session.execute(text("SET session_replication_role = 'origin';"))

        db.session.commit()
        return {"message": "All tables truncated successfully."}, 200

    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500

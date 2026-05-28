from flask import Blueprint, jsonify


migration_bp = Blueprint("migration", __name__, url_prefix="/api/migration")


@migration_bp.get("/health")
def migration_health():
    return jsonify({"ok": True, "service": "migration"})

from flask import Blueprint, jsonify


dataset_bp = Blueprint("dataset", __name__, url_prefix="/api/datasets")


@dataset_bp.get("/health")
def dataset_health():
    return jsonify({"ok": True, "service": "dataset"})

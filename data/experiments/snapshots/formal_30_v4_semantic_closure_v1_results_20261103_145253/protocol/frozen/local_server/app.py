from flask import Flask, jsonify

from local_server.api.dataset_routes import dataset_bp
from local_server.api.evaluation_routes import evaluation_bp
from local_server.api.migration_routes import migration_bp
from local_server.config import settings


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

    app.register_blueprint(dataset_bp)
    app.register_blueprint(evaluation_bp)
    app.register_blueprint(migration_bp)

    @app.get("/health")
    def health():
        return jsonify(
            {
                "ok": True,
                "service": "local_server",
                "provider": settings.llm_provider,
                "model": settings.llm_model,
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=settings.host, port=settings.port, debug=settings.debug)

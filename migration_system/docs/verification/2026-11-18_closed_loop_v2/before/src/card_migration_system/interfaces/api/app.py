from hmac import compare_digest
import io
from uuid import uuid4

from flask import Flask, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from ...application.service import Service, ServiceError, fields
from ...application.storage import StorageError


def create_app(settings, *, write_token):
    if type(write_token) is not str or len(write_token) < 24:
        raise ValueError("write_token_must_be_at_least_24_characters")
    app = Flask(__name__, static_folder=None)
    app.config.update(MAX_CONTENT_LENGTH=300000, ALLOWED_PORT=settings.port)
    service = Service(settings)
    app.extensions["migration_service"] = service

    @app.before_request
    def local_boundary():
        request.environ["cardmig.request_id"] = uuid4().hex
        allowed = request.host in (f"127.0.0.1:{app.config['ALLOWED_PORT']}",
                                   f"[::1]:{app.config['ALLOWED_PORT']}")
        if not allowed:
            raise ServiceError("host_not_allowed", 403)
        origin = request.headers.get("Origin")
        if origin is not None and origin != request.host_url.rstrip("/"):
            raise ServiceError("origin_not_allowed", 403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            supplied = request.headers.get("X-Cardmig-Token", "")
            if not compare_digest(supplied.encode(), write_token.encode()):
                raise ServiceError("write_token_required", 403)

    @app.after_request
    def safe_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(Exception)
    def error_response(error):
        if isinstance(error, ServiceError):
            code, status = error.code, error.status
        elif isinstance(error, StorageError):
            code, status = str(error), 409
        elif isinstance(error, HTTPException):
            code, status = error.name.replace(" ", "_").lower(), error.code
        else:
            code, status = "internal_execution_error", 500
        return jsonify(error={"code": code, "request_id": request.environ.get("cardmig.request_id")}), status

    @app.get("/health/live")
    def live():
        return jsonify(status="live", mode="development_stub", production_ready=False)

    @app.get("/health/ready")
    def ready():
        result, status = service.readiness()
        return jsonify(result), status

    @app.get("/api/v1/configurations")
    def configurations():
        return jsonify(mode="development_stub", production_ready=False,
                       profiles=["success", "repairable", "regression", "always_fail"],
                       max_repair_rounds=3, actual_model_calls=0)

    @app.get('/api/v1/generations/<generation_id>/report')
    def generation_report(generation_id):
        from ...application.generations import GenerationService
        return jsonify(GenerationService(service).report(generation_id))

    @app.get('/api/v1/generations/<generation_id>/artifact')
    def generation_artifact(generation_id):
        from ...application.generations import GenerationService
        content = GenerationService(service).download(generation_id)
        return send_file(io.BytesIO(content), mimetype='application/octet-stream', as_attachment=True,
                         download_name=f'offline_generation_{generation_id}.san')

    @app.get('/api/v1/ssm-extractions')
    def extractions():
        from ...application.extractions import ExtractionService
        raw_limit = request.args.get('limit', '10')
        if not raw_limit.isascii() or not raw_limit.isdecimal() or len(raw_limit) > 2 or not 1 <= int(raw_limit) <= 50:
            raise ServiceError('invalid_page_size', 400)
        return jsonify(ExtractionService(service).list_records(limit=int(raw_limit), before=request.args.get('before')))

    @app.get('/api/v1/ssm-extractions/<extraction_id>/report')
    def extraction_report(extraction_id):
        from ...application.extractions import ExtractionService
        return jsonify(ExtractionService(service).report(extraction_id))

    @app.get('/api/v1/ssm-extractions/<extraction_id>/artifact')
    def extraction_artifact(extraction_id):
        from ...application.extractions import ExtractionService
        content = ExtractionService(service).download(extraction_id)
        return send_file(io.BytesIO(content), mimetype='application/json',
                         as_attachment=True, download_name=f'ssm_{extraction_id}.json')

    @app.get("/")
    def workbench():
        directory = settings.project_root / "frontend/dist"
        if not (directory / "index.html").is_file():
            raise ServiceError("frontend_not_built", 503)
        response = send_from_directory(directory, "index.html")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        return response

    @app.get("/assets/<path:filename>")
    def frontend_asset(filename):
        return send_from_directory(settings.project_root / "frontend/dist/assets", filename)

    @app.post("/api/v1/inputs")
    def create_input():
        return jsonify(service.create_input(request.get_json())), 201

    @app.post("/api/v1/tasks")
    def create_task():
        return jsonify(service.create_task(request.get_json())), 201

    @app.get("/api/v1/tasks")
    def list_tasks():
        return jsonify(items=service.list_tasks())

    @app.post("/api/v1/tasks/<task_id>/runs")
    def enqueue(task_id):
        return jsonify(service.enqueue(task_id, request.get_json(), request.headers.get("Idempotency-Key"))), 202

    @app.get("/api/v1/runs/<run_id>")
    def run(run_id):
        return jsonify(service.run(run_id))

    @app.get("/api/v1/runs")
    def runs():
        raw_limit = request.args.get("limit", "10")
        if not raw_limit.isascii() or not raw_limit.isdecimal() or len(raw_limit) > 2:
            raise ServiceError("invalid_page_size", 400)
        return jsonify(service.list_runs(limit=int(raw_limit), before=request.args.get("before"),
                                         status=request.args.get("status")))

    @app.get("/api/v1/runs/<run_id>/events")
    def events(run_id):
        after = request.args.get("after", "0")
        if not after.isascii() or not after.isdecimal() or len(after) > 12:
            raise ServiceError("invalid_event_cursor", 400)
        return jsonify(items=service.events(run_id, int(after)))

    @app.get("/api/v1/runs/<run_id>/report")
    def report(run_id):
        return jsonify(service.report(run_id))

    @app.get("/api/v1/runs/<run_id>/artifact")
    def download(run_id):
        return send_file(io.BytesIO(service.download(run_id)), mimetype="application/octet-stream",
                         as_attachment=True, download_name="development_fixture.san")

    @app.post("/api/v1/runs/<run_id>/cancel")
    def cancel(run_id):
        fields(request.get_json(), ())
        service.cancel(run_id)
        return jsonify(service.run(run_id))

    @app.post("/api/v1/runs/<run_id>/resume")
    def resume(run_id):
        fields(request.get_json(), ())
        service.resume(run_id)
        return jsonify(service.run(run_id)), 202

    from .migrations import register_migration_routes
    register_migration_routes(app, service)
    return app

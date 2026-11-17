"""Real task endpoints reuse the enclosing API's token, origin and host boundaries."""
import io
import time
from flask import jsonify,request,send_file
from sqlalchemy import select
from ...application.migrations import MigrationService
from ...application.service import fields,ServiceError
from ...runtime import readiness
from ...persistence.database import transaction
from ...persistence.worker_health import WorkerHealth
from ...persistence.runtime_lock import execution_guard
from ...contracts.production_scope import production_scope


def register_migration_routes(app,base):
    service=MigrationService(base)

    @app.get('/api/v1/system/readiness')
    def system_readiness():
        result=readiness(base.settings)
        with transaction(base.engine) as s:
            workers=s.scalars(select(WorkerHealth).where(WorkerHealth.state=='migration_worker',WorkerHealth.last_seen>time.time()-30)).all()
        result['worker_online']=bool(workers)
        result['support_scope']=production_scope()
        return jsonify(result)

    @app.post('/api/v1/migrations')
    def create_migration():
        return jsonify(service.create(request.get_json(),request.headers.get('Idempotency-Key'))),202

    @app.get('/api/v1/migrations')
    def list_migrations():return jsonify(service.list())

    @app.get('/api/v1/migrations/<key>/report')
    def migration_report(key):return jsonify(service.report(key))

    @app.get('/api/v1/migrations/<key>/artifact')
    def migration_artifact(key):
        report=service.report(key);artifact=report['final_artifact']
        if not artifact:raise ServiceError('migration_artifact_not_available',404)
        return send_file(io.BytesIO(service.read_file(key,artifact['relative_path'])),mimetype='application/octet-stream',
            as_attachment=True,download_name=report['request']['filename'].replace('.vue','.san'))

    @app.get('/api/v1/migrations/<key>/files')
    def migration_file(key):
        relative=request.args.get('path','');content=service.read_file(key,relative)
        # All untrusted content is downloaded, not served as same-origin executable HTML/JS.
        return send_file(io.BytesIO(content),mimetype='application/octet-stream',as_attachment=True,
            download_name=relative.rsplit('/',1)[-1])

    @app.post('/api/v1/migrations/<key>/cancel')
    def migration_cancel(key):
        fields(request.get_json(),());service.cancel(key);return jsonify(service.report(key))

    @app.post('/api/v1/migrations/<key>/resume')
    def migration_resume(key):
        fields(request.get_json(),())
        with execution_guard(base.settings.runtime_dir):
            service.guard(key);row=service.job(key)
            if row.status not in ('review_required','blocked'):raise ServiceError('migration_not_resumable')
            if any(c['status']!='returned' for c in service.report(key)['calls']):raise ServiceError('model_response_unknown_no_automatic_retry')
            service.update(key,status='queued',stop_reason='resume_requested')
        return jsonify(service.report(key)),202

    @app.post('/api/v1/migrations/<key>/feedback')
    def migration_feedback(key):return jsonify(service.feedback(key,request.get_json())),201

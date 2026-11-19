"""Authenticated SQLite multi-user boundary. Local test mode stays explicit/separate."""
from hmac import compare_digest
from flask import g, jsonify, request
from ...application.accounts import AccountService,audit_event
from ...application.service import ServiceError, fields
from ...persistence.database import transaction


def install_accounts(app,base,anonymous_sessions):
    service=AccountService(base)
    multi=base.settings.auth_mode=='multi_user'
    def origin(): return base.settings.public_origin or request.host_url.rstrip('/')
    def cookie_name(): return 'cardmig_auth_'+str(app.config['ALLOWED_PORT'])
    def resolve(): return service.resolve(request.cookies.get(cookie_name()),origin())

    def session_response():
        if not multi:
            if request.path=='/api/v1/auth/session': return jsonify(mode='local',authenticated=False)
            return anonymous_sessions.bootstrap()
        current=resolve()
        if current:
            return jsonify(mode='multi_user',authenticated=True,user=current['user'],csrf_token=current['csrf_token'],expires_in=current['expires_in'])
        response=anonymous_sessions.bootstrap()
        data=response.get_json();data.update(mode='multi_user',authenticated=False,user=None)
        response.set_data(app.json.dumps(data));return response

    @app.before_request
    def authenticate():
        if not multi or not request.path.startswith('/api/v1/'): return
        g.account=None
        public=request.path in ('/api/v1/auth/session','/api/v1/browser-session','/api/v1/auth/login')
        current=resolve()
        if current:g.account=current
        if not public and not current:raise ServiceError('auth_required',401)
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('X-Cardmig-Token') is not None:raise ServiceError('script_token_disabled_in_multi_user',403)
            if current:
                supplied=request.headers.get('X-Cardmig-CSRF','')
                if not compare_digest(supplied.encode(),current['csrf_token'].encode()):raise ServiceError('browser_csrf_required',403)
            else:anonymous_sessions.authorize()
        if current and current['user']['must_change_password'] and request.path not in ('/api/v1/auth/session','/api/v1/browser-session','/api/v1/auth/password','/api/v1/auth/logout'):
            raise ServiceError('password_change_required',403)
        normal=request.path.startswith(('/api/v1/migrations','/api/v1/auth/','/api/v1/admin/')) or request.path in ('/api/v1/inputs','/api/v1/browser-session','/api/v1/system/readiness')
        if current and (request.path.startswith('/api/v1/admin/') or not normal) and current['user']['role']!='admin':raise ServiceError('admin_required',403)
        if current and request.path.startswith('/api/v1/migrations/'):
            service.authorize_job(current['user'],request.path.split('/')[4])

    def require_multi():
        if not multi:raise ServiceError('multi_user_mode_required',409)

    @app.get('/api/v1/auth/session')
    def auth_session():return session_response()

    @app.post('/api/v1/auth/login')
    def login():
        require_multi();payload=request.get_json();fields(payload,('username','password'),('username','password'))
        token,user=service.login(payload['username'],payload['password'],request.remote_addr or 'unknown',origin())
        response=jsonify(user=user)
        response.set_cookie(cookie_name(),token,max_age=service.lifetime,httponly=True,samesite='Strict',
                            secure=bool(base.settings.public_origin) or request.is_secure,path='/api/v1')
        return response

    @app.post('/api/v1/auth/logout')
    def logout():
        require_multi();fields(request.get_json(),())
        service.logout(g.account['session_id'],g.account['user']['id'])
        response=jsonify(status='logged_out');response.delete_cookie(cookie_name(),path='/api/v1',httponly=True,samesite='Strict');return response

    @app.get('/api/v1/auth/usage')
    def usage():require_multi();return jsonify(service.usage(g.account['user']['id']))

    @app.post('/api/v1/auth/password')
    def password():
        require_multi();payload=request.get_json();fields(payload,('current_password','new_password'),('current_password','new_password'))
        service.change_password(g.account['user']['id'],payload['current_password'],payload['new_password'])
        response=jsonify(status='password_changed_login_required');response.delete_cookie(cookie_name(),path='/api/v1');return response

    @app.get('/api/v1/admin/users')
    def users():require_multi();return jsonify(items=service.users())

    @app.post('/api/v1/admin/users')
    def create_user():require_multi();return jsonify(service.create_user(request.get_json(),g.account['user']['id'])),201

    @app.post('/api/v1/admin/users/<user_id>')
    def update_user(user_id):require_multi();return jsonify(service.manage_user(g.account['user']['id'],user_id,request.get_json()))

    @app.post('/api/v1/admin/users/<user_id>/limits')
    def update_limits(user_id):
        require_multi();service.set_limits(g.account['user']['id'],user_id,request.get_json());return jsonify(status='updated')

    @app.get('/api/v1/admin/audit')
    def audit():require_multi();return jsonify(items=service.audits())

    @app.after_request
    def audit_operations(response):
        if multi and getattr(g,'account',None) and 200<=response.status_code<300:
            path=request.path
            if path.startswith('/api/v1/migrations/') and (request.method=='POST' or path.endswith(('/files','/artifact'))):
                with transaction(base.engine) as s:
                    audit_event(s,g.account['user']['id'],'migration_'+path.rsplit('/',1)[-1],path.split('/')[4])
        return response

    return session_response

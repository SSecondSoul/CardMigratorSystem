"""Short-lived loopback browser authorization, independent of script write tokens.

Not user authentication: any process already controlling this machine can use the
local service. The custom bootstrap/write headers, host/origin checks and strict
HttpOnly cookie prevent ordinary foreign websites from authorizing writes.
"""
from hmac import compare_digest
import secrets

from flask import jsonify, request, current_app
from itsdangerous import BadSignature, URLSafeTimedSerializer

from ...application.service import ServiceError


class BrowserSessions:
    lifetime = 8 * 60 * 60

    def __init__(self):
        # Per-process signing key: restarting the API invalidates old sessions.
        self.signer = URLSafeTimedSerializer(secrets.token_urlsafe(32), salt="cardmig-browser-v1")

    def cookie_name(self):
        # Cookies do not isolate ports; keep parallel local workspaces separate.
        return "cardmig_session_" + request.host.rsplit(":", 1)[-1]

    def read(self):
        try:
            data = self.signer.loads(request.cookies.get(self.cookie_name(), ""), max_age=self.lifetime)
        except BadSignature:
            return None
        if (not isinstance(data, dict) or data.get("host") != request.host
                or type(data.get("csrf")) is not str or len(data["csrf"]) != 43):
            return None
        return data

    def bootstrap(self):
        # Not a navigable/login URL. A foreign website cannot add this header
        # without a CORS preflight, and this API never grants foreign CORS.
        if (request.headers.get("X-Cardmig-Session") != "bootstrap"
                or request.headers.get("Sec-Fetch-Site") not in (None, "same-origin")):
            raise ServiceError("browser_session_bootstrap_denied", 403)
        data = self.read() or {"host": request.host, "csrf": secrets.token_urlsafe(32)}
        response = jsonify(status="ready", csrf_token=data["csrf"], expires_in=self.lifetime)
        response.set_cookie(self.cookie_name(), self.signer.dumps(data), max_age=self.lifetime,
                            httponly=True, samesite="Strict", secure=request.is_secure or current_app.config.get('PUBLIC_HTTPS',False), path="/api/v1")
        return response

    def authorize(self):
        data = self.read()
        if data is None:
            raise ServiceError("browser_session_required", 403)
        supplied = request.headers.get("X-Cardmig-CSRF", "")
        if not compare_digest(supplied.encode(), data["csrf"].encode()):
            raise ServiceError("browser_csrf_required", 403)

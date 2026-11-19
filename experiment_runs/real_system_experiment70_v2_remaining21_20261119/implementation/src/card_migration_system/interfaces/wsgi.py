"""Production WSGI factory; operator supplies HTTPS proxy and a reviewed origin."""
import os
import secrets
from ..config import load_settings
from .api.app import create_app

def create_application():
    settings=load_settings(config_file=os.environ.get('CARDMIG_SYSTEM_CONFIG','configs/multi_user.toml'))
    if settings.auth_mode!='multi_user':raise ValueError('Public WSGI requires multi_user authentication')
    if not settings.public_origin:raise ValueError('Public WSGI requires explicit CARDMIG_PUBLIC_ORIGIN=https://your-domain')
    return create_app(settings,write_token=secrets.token_urlsafe(32))

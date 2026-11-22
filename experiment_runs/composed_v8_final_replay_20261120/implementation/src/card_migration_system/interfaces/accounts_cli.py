"""Explicit local administrator provisioning; credentials never enter command args."""
import argparse
import getpass
import json
from pathlib import Path
from sqlalchemy import select
from ..config import load_settings
from ..application.service import Service, ServiceError
from ..application.accounts import AccountService,password_hash,audit_event
from ..persistence.accounts import User
from ..persistence.database import transaction

COMMANDS={'init-admin','reset-admin-password'}
def main(argv):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=sorted(COMMANDS));parser.add_argument('--username',required=True)
    parser.add_argument('--project-root',type=Path);parser.add_argument('--config',type=Path,default=Path('configs/multi_user.toml'))
    args=parser.parse_args(argv);base=None
    try:
        settings=load_settings(project_root=args.project_root,config_file=args.config)
        if settings.auth_mode!='multi_user':raise ServiceError('multi_user_mode_required')
        password=getpass.getpass('New administrator password (12-128 characters): ')
        if password!=getpass.getpass('Repeat password: '):raise ServiceError('passwords_do_not_match')
        base=Service(settings);service=AccountService(base)
        if args.command=='init-admin':
            result=service.create_user({'username':args.username,'password':password,'role':'admin'},bootstrap=True)
        else:
            encoded=password_hash(password)
            with transaction(base.engine) as s:
                user=s.scalar(select(User).where(User.username_normalized==args.username.lower(),User.role=='admin'))
                if not user:raise ServiceError('admin_not_found')
                user.password_hash=encoded;user.is_active=True;user.must_change_password=False
                user.password_changed_at=__import__('time').time();service._revoke(s,user.id)
                audit_event(s,user.id,'admin_password_recovered',user.id)
            result={'username':args.username,'sessions_revoked':True}
        print(json.dumps({'status':'completed','account':result},ensure_ascii=True));return 0
    except (ValueError,EOFError) as error:
        print(json.dumps({'status':'blocked','error':getattr(error,'code',type(error).__name__)}));return 2
    finally:
        if base:base.close()

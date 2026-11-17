"""Interactive local browser QA fixture: real API/SQLite/worker, no paid clients.

Only disposable files; commands on stdin: worker-start, worker-once, facts, quit.
Never points at the user's runtime or old experiments.
"""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread

from test_scaffold import copy_fixture, PROJECT
from card_migration_system.config import load_settings
from card_migration_system.interfaces.api.app import create_app
from card_migration_system.persistence.database import initialize
from werkzeug.serving import make_server, WSGIRequestHandler

TOKEN = "test-only-workbench-write-token"


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def main():
    if not (PROJECT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build migration_system/frontend first")
    with TemporaryDirectory(prefix="cardmig-workbench-qa-") as temporary:
        project = copy_fixture(Path(temporary))
        shutil.copyfile(PROJECT / "requirements.lock", project / "requirements.lock")
        shutil.copytree(PROJECT / "migrations", project / "migrations", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(PROJECT / "frontend/dist", project / "frontend/dist")
        settings = load_settings(project_root=project, environ={})
        initialize(settings)
        app = create_app(settings, write_token=TOKEN)
        server = make_server("127.0.0.1", 0, app, request_handler=QuietHandler)
        app.config["ALLOWED_PORT"] = server.server_port
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        worker = None
        command = [sys.executable, str(PROJECT / "scripts/run_system.py"), "worker", "--project-root", str(project)]
        print(json.dumps({"scope": "temporary_development_browser_qa_no_model_calls",
                          "url": f"http://127.0.0.1:{server.server_port}", "test_only_token": TOKEN}), flush=True)
        try:
            for raw in sys.stdin:
                action = raw.strip()
                if action == "quit":
                    break
                if action == "worker-start":
                    if worker is None or worker.poll() is not None:
                        worker = subprocess.Popen(command, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    print(json.dumps({"worker_started": True}), flush=True)
                elif action == "worker-once":
                    result = subprocess.run(command + ["--once"], timeout=45, capture_output=True, text=True)
                    print(result.stdout, flush=True)
                elif action == "facts":
                    with closing(sqlite3.connect(settings.business_database)) as connection:
                        counts = {name: connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                                  for name in ("source_inputs", "tasks", "runs", "attempts", "artifact_revisions")}
                    print(json.dumps({"counts": counts, "model_calls": 0}), flush=True)
        finally:
            if worker is not None and worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=10)
            server.shutdown(); thread.join(timeout=5); server.server_close()
            app.extensions["migration_service"].close()


if __name__ == "__main__":
    main()

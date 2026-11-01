"""Shared configuration for WSGI requests and cPanel cron, no secret arguments."""
import json
import os
from pathlib import Path
from bot import connect

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / '.private'


def configuration():
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    path = PRIVATE / 'config.json'
    if path.exists():
        values = json.loads(path.read_text())
        for key, value in values.items():
            # cPanel environment settings take precedence over private config.
            os.environ.setdefault(key, str(value))
    os.environ.setdefault('DATABASE_PATH', str(PRIVATE / 'novasol.sqlite3'))


def database():
    configuration()
    db = connect(os.environ['DATABASE_PATH'])
    db.execute('''CREATE TABLE IF NOT EXISTS inbox (
      id INTEGER PRIMARY KEY, payload TEXT NOT NULL,
      status TEXT DEFAULT 'queued')''')
    db.commit()
    return db

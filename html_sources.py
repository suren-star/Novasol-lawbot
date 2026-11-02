"""Stage HTML source snapshots independently of AI and publishing."""
import datetime as dt
import hashlib
import json
import sqlite3
from arlis_source import ORIGIN, SourceError, act_url, fetch, recent_cards, evidence


def ledger(path):
    db = sqlite3.connect(path,timeout=30)
    db.executescript('''
      CREATE TABLE IF NOT EXISTS html_settings(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS html_versions(
        url TEXT NOT NULL, fingerprint TEXT NOT NULL, captured TEXT NOT NULL,
        baseline INTEGER NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL,
        PRIMARY KEY(url,fingerprint));
    ''')
    return db


def capture(db, urls, baseline=False, reader=evidence):
    initialized = db.execute("SELECT value FROM html_settings WHERE key='baseline'").fetchone()
    if bool(initialized) == bool(baseline):
        raise SourceError('Use baseline exactly once, then scan')
    # Finish source reads before committing: never record a partial successful scan.
    items = []
    for url in dict.fromkeys(act_url(u,latest=True) for u in urls):
        item = reader(url)
        if not item.get('text') or not item.get('comparison_complete'):
            raise SourceError('Incomplete source evidence')
        payload = json.dumps(item,ensure_ascii=False,sort_keys=True)
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        items.append((url,fingerprint,payload))
    if not items:
        raise SourceError('Empty discovery is not a verified scan')
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    added = 0
    with db:
        for url,fingerprint,payload in items:
            added += db.execute('INSERT OR IGNORE INTO html_versions VALUES(?,?,?,?,?,?)',
                (url,fingerprint,now,int(baseline),'baseline' if baseline else 'pending_review',payload)).rowcount
        if baseline:
            db.execute("INSERT INTO html_settings VALUES('baseline',?)",(now,))
        db.execute("INSERT OR REPLACE INTO html_settings VALUES('last_scan',?)",(now,))
    return added


def main():
    import fcntl
    import os
    import sys
    from hosting import PRIVATE, configuration
    os.umask(0o077)
    configuration()
    command = sys.argv[1] if len(sys.argv)>1 else 'status'
    with open(PRIVATE / 'html-sources.lock','a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('HTML source job already running.')
            return
        db = ledger(PRIVATE / 'html-sources.sqlite3')
        try:
            if command in ('baseline','scan'):
                cards = recent_cards(fetch(ORIGIN + '/hy/'))
                print('Discovery scope: recent homepage cards ONLY; daily coverage incomplete.',flush=True)
                print('New snapshots:',capture(db,cards,baseline=command=='baseline'))
            elif command == 'status':
                print('Snapshots by status:',db.execute('SELECT status,count(*) FROM html_versions GROUP BY status').fetchall())
            else:
                raise ValueError('Use: html_sources.py baseline | scan | status')
            print('PDF/AI/Telegram requests: 0. Collection setting unchanged.')
        finally:
            db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('HTML source job failed:',type(exc).__name__)
        raise SystemExit(1)

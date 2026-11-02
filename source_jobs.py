"""Explicit opt-in source inventory/extraction commands, independent of publishing."""
import fcntl
import json
import os
import sys
from hosting import PRIVATE, configuration
from pdf_sources import ledger, scan, extract_pending


def review(db):
    rows = db.execute("SELECT url,title FROM source_records WHERE status='manual_review' ORDER BY url").fetchall()
    print('Documents requiring review:',len(rows))
    for url,title in rows:
        print('Title:',title)
        print('Source:',url)
        version = db.execute('SELECT pages,warnings FROM source_versions WHERE url=? ORDER BY id DESC LIMIT 1',(url,)).fetchone()
        if version:
            pages,warnings = version
            flagged = json.loads(warnings)
            print('PDF pages:',pages)
            print('Flagged pages:',[p for p in flagged if p > 0])
            if 0 in flagged:
                print('Document warning: too little text or low Armenian character ratio.')
            if any(p > 0 for p in flagged):
                print('Page warning: too little readable text or replacement characters; inspect original pages.')
            if not flagged:
                print('Extraction warnings: none stored; inspect original document.')
        else:
            print('No extracted version stored.')
        error = db.execute('SELECT error_type FROM source_errors WHERE url=? ORDER BY id DESC LIMIT 1',(url,)).fetchone()
        if error:
            print('Last saved error type:',error[0])
        if not version and not error:
            print('Reason not recorded by the installed extractor version.')
    print('Review only: no statuses changed; no downloads performed.')


def main():
    os.umask(0o077)
    configuration()
    command = sys.argv[1] if len(sys.argv)>1 else 'status'
    with open(PRIVATE / 'sources.lock','a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('A source job is already running.')
            return
        db = ledger(PRIVATE / 'sources.sqlite3')
        try:
            if command in ('baseline','scan'):
                report = scan(db,baseline=command=='baseline')
                print('Inventory:',report)
                print('Scope: laws (11), government decisions (15), subordinate normative acts (16).')
                print('Weekly rolling lists only; other categories and archive gaps are not covered.')
            elif command == 'extract':
                print('Extraction results:',extract_pending(db))
            elif command == 'status':
                print('Records:',db.execute('SELECT count(*) FROM source_records').fetchone()[0])
                print('Versions:',db.execute('SELECT count(*) FROM source_versions').fetchone()[0])
                print('By status:',db.execute('SELECT status,count(*) FROM source_records GROUP BY status').fetchall())
            elif command == 'review':
                review(db)
            else:
                print('Use: source_jobs.py baseline | scan | extract | status | review')
            print('No AI requests or Telegram posts. Main collection setting unchanged.')
        finally:
            db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Source job failed:',type(exc).__name__)
        raise SystemExit(1)

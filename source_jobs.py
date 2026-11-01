"""Explicit opt-in source inventory/extraction commands, independent of publishing."""
import fcntl
import os
import sys
from hosting import PRIVATE, configuration
from pdf_sources import ledger, scan, extract_pending


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
            else:
                print('Use: source_jobs.py baseline | scan | extract | status')
            print('No AI requests or Telegram posts. Main collection setting unchanged.')
        finally:
            db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Source job failed:',type(exc).__name__)
        raise SystemExit(1)

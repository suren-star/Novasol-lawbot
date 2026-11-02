"""Discover official release categories and scan them without AI/publication."""
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from arlis_source import ORIGIN, Tree, SourceError, fetch, weekly_files
from pdf_sources import pdf_url

LEGACY_SECTIONS = {11,15,16}


def release_sections(html):
    result = {}
    for node in Tree(html).root.nodes():
        if node.tag != 'a' or not node.has('service-card'):
            continue
        match = re.fullmatch(r'/hy/releases/(\d+)/?',node.attrs.get('href',''))
        if match:
            result[int(match[1])] = node.text()
    if not LEGACY_SECTIONS.issubset(result):
        raise SourceError('Official release category discovery incomplete')
    return result


def inventory(loader=fetch, file_loader=weekly_files, progress=None):
    sections = release_sections(loader(ORIGIN+'/hy/releases'))
    results = {}
    # Read-only requests; limit concurrency to avoid flooding the public site.
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(file_loader,ident):ident for ident in sections}
        errors=[]
        for job in as_completed(jobs):
            ident=jobs[job]
            try:
                results[ident]=job.result()
                if progress: progress(ident,sections[ident],len(results[ident]))
            except Exception as exc:
                errors.append((ident,type(exc).__name__))
        if errors:
            raise SourceError('Category reads failed: '+str(sorted(errors)))
    return sections,results


def commit_inventory(db,sections,records):
    if set(sections)!=set(records) or not LEGACY_SECTIONS.issubset(sections):
        raise SourceError('Refusing partial category inventory')
    if not db.execute("SELECT 1 FROM source_settings WHERE key='baseline'").fetchone():
        raise SourceError('Existing initial baseline required')
    initialized = LEGACY_SECTIONS | {
        int(key.split(':')[1]) for key, in db.execute(
            "SELECT key FROM source_settings WHERE key GLOB 'wide_section:[0-9]*'")}
    first_sections = set(sections)-initialized
    combined={}
    for section,items in records.items():
        for raw_url,title in items.items():
            url=pdf_url(raw_url)
            value=combined.setdefault(url,{'title':title,'sections':set()})
            value['sections'].add(section)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    new=baseline=0
    with db:
        for url,item in combined.items():
            # New categories start with a baseline. A document also discovered
            # in an already monitored category remains genuinely new there.
            is_baseline = not bool(item['sections'] & initialized)
            inserted=db.execute('''INSERT OR IGNORE INTO source_records
              (url,title,first_seen,last_seen,is_baseline) VALUES(?,?,?,?,?)''',
              (url,item['title'],now,now,int(is_baseline))).rowcount
            if inserted:
                if is_baseline: baseline+=1
                else: new+=1
            # Never reset status, extracted versions or existing baseline flags.
            db.execute('UPDATE source_records SET last_seen=? WHERE url=?',(now,url))
            for section in item['sections']:
                db.execute('INSERT OR IGNORE INTO source_sections VALUES(?,?)',(url,section))
        for section in sections:
            db.execute('INSERT OR IGNORE INTO source_settings VALUES(?,?)',
                       ('wide_section:'+str(section),now))
        db.execute("INSERT OR REPLACE INTO source_settings VALUES('last_wide_scan',?)",(now,))
    return {'new_records':new,'additional_baseline_records':baseline,
            'first_scan_sections':sorted(first_sections),
            'unique_records':db.execute('SELECT count(*) FROM source_records').fetchone()[0]}


def main():
    import fcntl
    import os
    import sys
    from hosting import PRIVATE, configuration
    from pdf_sources import ledger
    command=sys.argv[1] if len(sys.argv)>1 else 'check'
    if command not in ('check','scan'):
        raise SourceError('Use: wide_sources.py check | scan')
    def progress(ident,title,count):
        print('Section',ident,'|',title,'| PDF records:',count,flush=True)
    if command=='check':
        sections,records=inventory(progress=progress)
        print('Discovered categories:',len(sections))
        print('Unique current PDF links:',len({u for items in records.values() for u in items}))
        print('Database writes: 0.')
    else:
        os.umask(0o077)
        configuration()
        if not (PRIVATE/'sources.sqlite3').exists():
            raise SourceError('Source ledger missing; initial baseline required')
        # Share the source_jobs lock, so inventory and extraction cannot overlap.
        with open(PRIVATE/'sources.lock','a') as lock:
            try:
                fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print('Another source job is running.')
                return
            sections,records=inventory(progress=progress)
            db=ledger(PRIVATE/'sources.sqlite3')
            try:
                print('Wide inventory:',commit_inventory(db,sections,records))
            finally:
                db.close()
    print('Scope: current rolling PDF lists in discovered release categories; NOT full daily/archive coverage.')
    print('AI calls: 0; Telegram posts: 0; collection setting unchanged.')


if __name__=='__main__':
    try:
        main()
    except SourceError as exc:
        print('Wide source check failed:',str(exc))
        raise SystemExit(1)
    except Exception as exc:
        print('Wide source check failed:',type(exc).__name__)
        raise SystemExit(1)

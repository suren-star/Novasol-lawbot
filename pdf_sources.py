"""Read official PDFs and keep a durable ledger, without AI or publication."""
import datetime as dt
import hashlib
import io
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from arlis_source import ORIGIN, SourceError, weekly_files

MAX_BYTES = 20_000_000
MAX_PAGES = 150


class ManualReview(SourceError):
    pass


def pdf_url(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in ('arlis.am','www.arlis.am')
            or not re.fullmatch(r'/releases/files/\d+/[a-f0-9]+', parsed.path)
            or parsed.query or parsed.fragment):
        raise SourceError('Unexpected official PDF URL')
    return ORIGIN + parsed.path


def download(url):
    url = pdf_url(url)
    req = urllib.request.Request(url, headers={'User-Agent':'NovasolLawBot/0.3 (official publication reader)'})
    with urllib.request.urlopen(req, timeout=30) as response:
        parsed = urllib.parse.urlsplit(response.url)
        if parsed.scheme != 'https' or parsed.hostname not in ('arlis.am','www.arlis.am','old.arlis.am'):
            raise SourceError('Unexpected PDF redirect')
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ManualReview('PDF exceeds size limit')
    if not body.startswith(b'%PDF-'):
        raise SourceError('Source did not return a PDF')
    return body


def extract_pdf(body):
    from pypdf import PdfReader
    if not body.startswith(b'%PDF-'):
        raise SourceError('Invalid PDF signature')
    if len(body) > MAX_BYTES:
        raise ManualReview('PDF exceeds size limit')
    reader = PdfReader(io.BytesIO(body), strict=False)
    if reader.is_encrypted:
        raise ManualReview('Encrypted PDF requires manual review')
    if not 0 < len(reader.pages) <= MAX_PAGES:
        raise ManualReview('PDF page count exceeds extraction limit')
    pages, uncertain = [], []
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or '').strip()
        # Scans, broken fonts, blank pages and annex images must not be silently
        # dropped from a supposedly complete legal source.
        if len(re.findall(r'\w', text)) < 20 or '\ufffd' in text:
            uncertain.append(index)
        pages.append(text)
    if sum(len(x) for x in pages) > 500_000:
        raise ManualReview('Extracted PDF text exceeds size limit')
    text = '\n\n'.join(f'[PAGE {i}]\n{value}' for i,value in enumerate(pages,1))
    letters = sum(c.isalpha() for c in text)
    armenian = sum('\u0531' <= c <= '\u0587' for c in text)
    if letters and armenian / letters < .1:
        uncertain.append(0)  # Wrong encoding/language is not safe Armenian input.
    if len(text.strip()) < 100:
        uncertain.append(0)
    links = set()
    for page in reader.pages:
        for reference in page.get('/Annots', []):
            annotation = reference.get_object()
            action = annotation.get('/A')
            if action:
                action = action.get_object()
                uri = str(action.get('/URI', ''))
                parsed = urllib.parse.urlsplit(uri)
                if parsed.scheme == 'https' and parsed.hostname in ('arlis.am','www.arlis.am','old.arlis.am'):
                    links.add(uri)
    return {'pages':len(pages), 'text':text, 'sha256':hashlib.sha256(body).hexdigest(),
            'armenian_characters':armenian, 'uncertain_pages':sorted(set(uncertain)),
            'status':'manual_review' if uncertain else 'extracted', 'official_links':sorted(links)}


def ledger(path):
    db = sqlite3.connect(path, timeout=30)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS source_settings(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS source_records(
        url TEXT PRIMARY KEY, title TEXT NOT NULL, first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL, is_baseline INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending');
      CREATE TABLE IF NOT EXISTS source_sections(
        url TEXT REFERENCES source_records(url), section INTEGER,
        PRIMARY KEY(url,section));
      CREATE TABLE IF NOT EXISTS source_versions(
        id INTEGER PRIMARY KEY, url TEXT REFERENCES source_records(url),
        sha256 TEXT NOT NULL, captured TEXT NOT NULL, pages INTEGER NOT NULL,
        text TEXT NOT NULL, status TEXT NOT NULL, warnings TEXT NOT NULL,
        official_links TEXT NOT NULL, UNIQUE(url,sha256));
      CREATE TABLE IF NOT EXISTS source_errors(
        id INTEGER PRIMARY KEY, url TEXT REFERENCES source_records(url),
        captured TEXT NOT NULL, error_type TEXT NOT NULL);
    ''')
    return db


def record_inventory(db, inventories, baseline=False):
    """Commit only after ALL requested listing sections have been fetched."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    initialized = db.execute("SELECT value FROM source_settings WHERE key='baseline'").fetchone()
    if not initialized and not baseline:
        raise SourceError('Run an explicit initial baseline before scanning for new records')
    if initialized and baseline:
        raise SourceError('Baseline already exists; refusing to hide newly discovered publications')
    added = 0
    with db:
        for section, records in inventories.items():
            for url,title in records.items():
                url = pdf_url(url)
                added += db.execute('''INSERT OR IGNORE INTO source_records
                  (url,title,first_seen,last_seen,is_baseline) VALUES(?,?,?,?,?)''',
                  (url,title,now,now,int(baseline))).rowcount
                db.execute('UPDATE source_records SET title=?,last_seen=? WHERE url=?',(title,now,url))
                db.execute('INSERT OR IGNORE INTO source_sections VALUES(?,?)',(url,int(section)))
        if baseline:
            db.execute("INSERT INTO source_settings VALUES('baseline',?)",(now,))
        db.execute("INSERT OR REPLACE INTO source_settings VALUES('last_scan',?)",(now,))
    return added


def save_version(db, url, item):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with db:
        inserted = db.execute('''INSERT OR IGNORE INTO source_versions
          (url,sha256,captured,pages,text,status,warnings,official_links)
          VALUES(?,?,?,?,?,?,?,?)''', (url,item['sha256'],now,item['pages'],item['text'],
          item['status'],json.dumps(item['uncertain_pages']),json.dumps(item['official_links']))).rowcount
        db.execute('UPDATE source_records SET status=? WHERE url=?',(item['status'],url))
    return bool(inserted)


def scan(db, sections=(11,15,16), baseline=False, loader=weekly_files):
    inventories = {section:loader(section) for section in sections}
    added = record_inventory(db,inventories,baseline=baseline)
    return {'new_records':added,'unique_records':db.execute('SELECT count(*) FROM source_records').fetchone()[0],
            'sections':{key:len(value) for key,value in inventories.items()}}


def extract_pending(db, limit=3, downloader=download, extractor=extract_pdf):
    result = []
    for url, in db.execute("SELECT url FROM source_records WHERE status='pending' ORDER BY first_seen,url LIMIT ?",(limit,)).fetchall():
        try:
            item = extractor(downloader(url))
            added = save_version(db,url,item)
            result.append({'status':item['status'],'pages':item['pages'],'stored_new_version':added})
        except Exception as exc:
            with db:
                db.execute("UPDATE source_records SET status='manual_review' WHERE url=?",(url,))
                db.execute('INSERT INTO source_errors(url,captured,error_type) VALUES(?,?,?)',
                           (url,dt.datetime.now(dt.timezone.utc).isoformat(),type(exc).__name__))
            result.append({'status':'manual_review','reason':type(exc).__name__})
    return result

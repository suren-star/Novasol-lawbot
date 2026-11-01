"""Fast authenticated Telegram webhook: queues updates for the minute cron job."""
import hmac
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hosting import database, configuration


def application(environ, start_response):
    def reply(status, text):
        body = text.encode()
        start_response(status, [('Content-Type', 'text/plain; charset=utf-8'),
                                ('Content-Length', str(len(body)))])
        return [body]

    path = environ.get('PATH_INFO', '')
    try:
        configuration()
    except Exception:
        return reply('503 Service Unavailable', 'Configuration incomplete')
    # Passenger can pass either a mount-relative or full path for a sub-URI.
    mount = urlsplit(os.getenv('PUBLIC_APP_URL', '')).path.rstrip('/')
    if mount and (path == mount or path.startswith(mount + '/')):
        path = path[len(mount):] or '/'
    path = path.rstrip('/') or '/'
    if environ.get('REQUEST_METHOD') == 'GET' and path in ('', '/', '/health'):
        return reply('200 OK', 'Novasol webhook online. Deployment is not proof of source coverage.')
    if path == '/telegram' and environ.get('REQUEST_METHOD') != 'POST':
        return reply('405 Method Not Allowed', 'Telegram endpoint ready; POST required.')
    if path != '/telegram' or environ.get('REQUEST_METHOD') != 'POST':
        return reply('404 Not Found', 'Not found')
    try:
        configuration()
        expected = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
        provided = environ.get('HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN', '')
        if not expected:
            return reply('503 Service Unavailable', 'Configuration incomplete')
        if not hmac.compare_digest(expected, provided):
            return reply('403 Forbidden', 'Forbidden')
        try:
            length = int(environ.get('CONTENT_LENGTH', '0'))
            if not 0 < length <= 1048576:
                return reply('413 Content Too Large', 'Invalid body size')
            payload = json.loads(environ['wsgi.input'].read(length))
            if not isinstance(payload, dict) or type(payload.get('update_id')) is not int:
                raise ValueError('Invalid update')
        except (ValueError, TypeError):
            return reply('400 Bad Request', 'Invalid update')
        db = database()
        try:
            with db:
                db.execute('INSERT OR IGNORE INTO inbox(id,payload) VALUES(?,?)',
                           (payload['update_id'], json.dumps(payload)))
        finally:
            db.close()
        return reply('200 OK', 'Queued')
    except Exception:
        # No credentials, paths, request bodies or stack traces in HTTP responses.
        return reply('503 Service Unavailable', 'Temporarily unavailable')

import io
import json
import os
import unittest
from unittest.mock import patch
from bot import connect
from passenger_wsgi import application


class WebhookTests(unittest.TestCase):
    @patch('passenger_wsgi.configuration')
    def test_mounted_endpoint_reaches_authentication(self, config):
        for path in ('/telegram', '/lawbot/telegram', '/lawbot/telegram/'):
            status = []
            with patch.dict(os.environ, {'PUBLIC_APP_URL':'https://novasol.am/lawbot', 'TELEGRAM_WEBHOOK_SECRET':'expected'}):
                application({'PATH_INFO':path, 'REQUEST_METHOD':'POST'}, lambda s,h:status.append(s))
            self.assertEqual(status, ['403 Forbidden'])

    @patch('passenger_wsgi.configuration')
    def test_get_endpoint_is_distinguishable_from_missing_route(self, config):
        status = []
        with patch.dict(os.environ, {'PUBLIC_APP_URL':'https://novasol.am/lawbot'}):
            result = application({'PATH_INFO':'/lawbot/telegram', 'REQUEST_METHOD':'GET'}, lambda s,h:status.append(s))
        self.assertEqual(status, ['405 Method Not Allowed'])
        self.assertIn(b'POST required', b''.join(result))

    def invoke(self, secret='test', payload=None):
        data = json.dumps(payload or {'update_id': 1}).encode()
        status = []
        body = application({'PATH_INFO':'/telegram', 'REQUEST_METHOD':'POST',
                            'CONTENT_LENGTH':str(len(data)), 'wsgi.input':io.BytesIO(data),
                            'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN':secret},
                           lambda value, headers: status.append(value))
        return status[0], b''.join(body)

    @patch('passenger_wsgi.configuration')
    def test_rejects_wrong_secret_without_opening_database(self, config):
        with patch.dict(os.environ, {'TELEGRAM_WEBHOOK_SECRET':'expected'}), patch('passenger_wsgi.database') as db:
            self.assertEqual(self.invoke('wrong')[0], '403 Forbidden')
            db.assert_not_called()

    @patch('passenger_wsgi.configuration')
    def test_missing_secret_fails_closed(self, config):
        with patch.dict(os.environ, {'TELEGRAM_WEBHOOK_SECRET':''}):
            self.assertEqual(self.invoke()[0], '503 Service Unavailable')

    @patch('passenger_wsgi.configuration')
    def test_duplicate_update_is_stored_once(self, config):
        # Wrapper prevents the WSGI adapter from closing the in-memory test DB.
        db = connect(':memory:')
        db.execute("CREATE TABLE inbox(id INTEGER PRIMARY KEY,payload TEXT,status TEXT DEFAULT 'queued')")
        class Wrapper:
            def __enter__(self): return db.__enter__()
            def __exit__(self, *args): return db.__exit__(*args)
            def execute(self, *args): return db.execute(*args)
            def close(self): pass
        with patch.dict(os.environ, {'TELEGRAM_WEBHOOK_SECRET':'test'}), patch('passenger_wsgi.database', return_value=Wrapper()):
            self.assertEqual(self.invoke()[0], '200 OK')
            self.assertEqual(self.invoke()[0], '200 OK')
            self.assertEqual(db.execute('SELECT count(*) FROM inbox').fetchone()[0], 1)
        db.close()

    @patch('passenger_wsgi.configuration')
    def test_invalid_update_is_rejected(self, config):
        with patch.dict(os.environ, {'TELEGRAM_WEBHOOK_SECRET':'test'}):
            self.assertEqual(self.invoke(payload={'update_id':'not-an-integer'})[0], '400 Bad Request')


if __name__ == '__main__':
    unittest.main()

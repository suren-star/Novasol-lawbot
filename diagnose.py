"""Local configuration checks. Never prints secret values or file contents."""
import json
import os
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    path = root / '.private' / 'config.json'
    print('Application folder:', root)
    print('Config exists:', path.is_file())
    values = {}
    if path.is_file():
        try:
            text = path.read_text(encoding='utf-8-sig')
            values = json.loads(text)
            if not isinstance(values, dict):
                print('JSON must be an object, not a list or string')
                return
            print('JSON format: OK')
            print('UTF-8 BOM present:', path.read_bytes().startswith(b'\xef\xbb\xbf'))
        except json.JSONDecodeError as exc:
            print('Invalid JSON at line', exc.lineno, 'column', exc.colno)
            return
        except Exception as exc:
            print('Cannot read config:', type(exc).__name__)
            return
    for key in ('TELEGRAM_BOT_TOKEN', 'PUBLIC_APP_URL', 'TELEGRAM_WEBHOOK_SECRET',
                'ADMIN_CHAT_ID', 'OPENAI_API_KEY', 'OPENAI_MODEL'):
        file_ok = isinstance(values.get(key), (str, int)) and bool(str(values.get(key, '')).strip())
        env_ok = bool(os.getenv(key, '').strip())
        print(key + ': file=' + ('SET' if file_ok else 'MISSING/EMPTY') +
              '; environment=' + ('SET' if env_ok else 'NOT SET'))
    try:
        from hosting import configuration, database
        configuration()
        print('Configuration loader: OK')
        db = database()
        db.close()
        print('Database initialization: OK')
    except Exception as exc:
        print('Configuration/database error:', type(exc).__name__)
        return
    for key in ('TELEGRAM_BOT_TOKEN', 'PUBLIC_APP_URL', 'TELEGRAM_WEBHOOK_SECRET'):
        print(key + ' effective: ' + ('SET' if os.getenv(key, '').strip() else 'MISSING/EMPTY'))
    print('No network requests made; no credentials displayed.')

if __name__ == '__main__':
    main()

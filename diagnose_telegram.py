"""Read-only Telegram connection diagnostics. Does not register or change webhook."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from hosting import configuration

def main():
    try:
        configuration()
    except Exception as exc:
        print('Configuration error:', type(exc).__name__)
        return
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    secret = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
    url = os.getenv('PUBLIC_APP_URL', '')
    print('Token format:', 'OK' if re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token) else 'INVALID')
    print('Webhook secret format:', 'OK' if re.fullmatch(r'[A-Za-z0-9_-]{1,256}', secret) else 'INVALID: use 1-256 Latin letters, numbers, underscore or hyphen')
    try:
        parsed = urllib.parse.urlsplit(url)
        valid_url = parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.query and not parsed.fragment
    except ValueError:
        valid_url = False
    print('App URL format:', 'OK' if valid_url else 'INVALID')
    print('App URL matches expected:', url.rstrip('/') == 'https://novasol.am/lawbot')
    if not token or not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        print('Correct the token privately in config.json; do not share it.')
        return
    def sanitize(value):
        value = str(value)
        for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_WEBHOOK_SECRET','OPENAI_API_KEY','PUBLIC_APP_URL'):
            item = os.getenv(key, '')
            if item:
                value = value.replace(item, '[redacted]')
        value = re.sub(r'https?://\S+', '[URL redacted]', value)
        return re.sub(r'[0-9]{6,}:[A-Za-z0-9_-]+', '[token redacted]', value)[:500]
    for method in ('getMe', 'getWebhookInfo'):
        req = urllib.request.Request('https://api.telegram.org/bot' + token + '/' + method,
                                     data=b'{}', headers={'Content-Type':'application/json'})
        try:
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    status, body = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, body = exc.code, exc.read()
            print(method + ' HTTP status:', status)
            try:
                result = json.loads(body)
            except ValueError:
                print('Response is not JSON; possible hosting proxy/security page')
                continue
            print(method + ' API success:', result.get('ok', False))
            if not result.get('ok'):
                print('Telegram error code:', result.get('error_code'))
                print('Telegram description:', sanitize(result.get('description', '')))
            elif method == 'getMe':
                print('Expected bot:', result.get('result',{}).get('username','').lower() == 'novasol_lawbot')
            else:
                info = result.get('result',{})
                print('Webhook registered:', bool(info.get('url')))
                print('Webhook matches expected:', info.get('url','') == 'https://novasol.am/lawbot/telegram')
                print('Pending updates:', info.get('pending_update_count',0))
                if info.get('last_error_message'):
                    print('Webhook delivery error:', sanitize(info['last_error_message']))
        except (urllib.error.URLError, TimeoutError):
            print('Network/TLS/timeout failure reaching Telegram; no credential values printed')
        except Exception as exc:
            print('Diagnostic failure:', type(exc).__name__)

if __name__ == '__main__':
    main()

"""cPanel setup and once-per-minute scheduled maintenance."""
import datetime as dt
import fcntl
import getpass
import json
import os
import secrets
import sys
import urllib.parse
from zoneinfo import ZoneInfo
from bot import Bot, APIError
from hosting import PRIVATE, configuration, database


def configure():
    configuration()
    path = PRIVATE / 'config.json'
    values = json.loads(path.read_text()) if path.exists() else {}
    print('Enter secrets only here in the private hosting terminal; input is hidden.')
    for key, label in [('TELEGRAM_BOT_TOKEN', 'Replacement Telegram bot token'),
                       ('OPENAI_API_KEY', 'OpenAI API key')]:
        value = getpass.getpass(label + ' (Enter keeps existing): ').strip()
        if value:
            values[key] = value
    admin = input('Your numeric Telegram ID (0 for initial /id setup; Enter keeps existing): ').strip()
    if admin:
        if not admin.isdigit():
            raise ValueError('Telegram ID must be numeric')
        values['ADMIN_CHAT_ID'] = admin
    model = input('OpenAI model ID (Enter keeps existing): ').strip()
    if model:
        values['OPENAI_MODEL'] = model
    url = input('HTTPS app URL, e.g. https://novasol.am/lawbot (Enter keeps existing): ').strip().rstrip('/')
    if url:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('Use a plain HTTPS application URL')
        values['PUBLIC_APP_URL'] = url
    values.setdefault('TELEGRAM_WEBHOOK_SECRET', secrets.token_urlsafe(32))
    temp = PRIVATE / 'config.json.tmp'
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(values, stream)
    os.replace(temp, path)
    os.chmod(path, 0o600)
    print('Private configuration saved. Restart the Python application if it was already running.')


def tick(bot):
    # Process Telegram first; collection failures must not block subscriptions.
    for ident, payload in bot.db.execute("SELECT id,payload FROM inbox WHERE status='queued' ORDER BY id LIMIT 50").fetchall():
        with bot.db:
            bot.db.execute("UPDATE inbox SET status='processing' WHERE id=?", (ident,))
        try:
            bot.update(json.loads(payload))
        except Exception:
            with bot.db:
                bot.db.execute("UPDATE inbox SET status='review' WHERE id=?", (ident,))
            print('Telegram update requires operator review', flush=True)
        else:
            with bot.db:
                bot.db.execute("UPDATE inbox SET status='done',payload='{}' WHERE id=?", (ident,))
    bot.deliver()
    now = dt.datetime.now(ZoneInfo('Asia/Yerevan'))
    today = now.date().isoformat()
    # Collection is disabled until source coverage is validated before launch.
    if os.getenv('COLLECTION_ENABLED', '').lower() == 'true' and now.hour >= 10 and bot.get('collected') != today:
        try:
            bot.collect()
        except Exception:
            print('Collection failed; existing drafts remain available', flush=True)
        else:
            bot.set('collected', today)
    if bot.admin:
        bot.notify()


def main():
    os.umask(0o077)
    command = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if command == 'configure':
        configure()
        return
    configuration()
    db = database()
    try:
        bot = Bot(db)
        if command == 'set-webhook':
            base = os.environ['PUBLIC_APP_URL'].rstrip('/')
            if not base.startswith('https://'):
                raise ValueError('HTTPS required')
            bot.api('setWebhook', url=base + '/telegram',
                    secret_token=os.environ['TELEGRAM_WEBHOOK_SECRET'],
                    allowed_updates=['message', 'callback_query'], max_connections=1)
            print('Telegram webhook registered. Minute cron is required for replies.')
        elif command == 'check':
            me = bot.api('getMe')
            info = bot.api('getWebhookInfo')
            print('Bot username:', me.get('username'))
            print('Webhook configured:', bool(info.get('url')))
            print('Pending Telegram updates:', info.get('pending_update_count', 0))
            print('Administrator configured:', bool(bot.admin))
            print('AI configured:', bool(bot.ai_key and bot.model))
            print('Collection enabled:', os.getenv('COLLECTION_ENABLED', '').lower() == 'true')
        elif command == 'check-channel':
            if not bot.channel:
                raise ValueError('TELEGRAM_CHANNEL_ID missing')
            me = bot.api('getMe')
            chat = bot.api('getChat', chat_id=bot.channel)
            member = bot.api('getChatMember', chat_id=bot.channel, user_id=me['id'])
            print('Channel configured:', bot.channel)
            print('Chat type:', chat.get('type'))
            print('Bot status:', member.get('status'))
            print('Can post:', member.get('status') == 'creator' or (member.get('status') == 'administrator' and member.get('can_post_messages') is True))
            print('No messages published.')
        elif command == 'tick':
            with open(PRIVATE / 'tick.lock', 'a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                tick(bot)
        else:
            print('Use: python manage.py configure | set-webhook | check | tick')
    finally:
        db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Command failed:', type(exc).__name__, '— check private configuration and hosting logs.')
        sys.exit(1)

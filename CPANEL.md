# cPanel / name.am deployment — Python 3.11

The WSGI app queues Telegram webhook updates. A cron command runs each minute to process subscriptions, approvals, deliveries, and the daily collection check. No persistent polling process is required. Replies can take about a minute, or longer while a collection batch is running.

## Application settings

- Python: 3.11.18
- Application root: `novasol-lawbot`, outside the public document root
- Application URL: `https://novasol.am/lawbot`
- Startup file: `passenger_wsgi.py`
- Entry point: `application`

## Install source

Use the activation command displayed at the top of the application's cPanel page. Do not guess your account's home directory. In that application's directory, download the repository code through cPanel Git or upload the individual source files from GitHub. Keep cPanel-generated files; back up any generated `passenger_wsgi.py` before replacing it with this repository's version. Do not run `git clone` over a nonempty directory.

The project needs no third-party Python packages. Upload bot.py, hosting.py, passenger_wsgi.py, manage.py and the documentation. Test files may be included. Never upload .private or real credentials to GitHub.

## Private setup

In the activated hosting terminal, inside the application directory:

```
python manage.py configure
```

Tokens are entered with hidden terminal input, not as command arguments or browser URLs. The script creates `.private/config.json` with permissions 600 in a directory with permissions 700. Keep the application directory OUTSIDE the public document root. WSGI environment variables override this private file; avoid conflicting values. Unlike cPanel web-app environment variables, the private file is also available to cron.

For initial administrator setup, use ID 0. AI model may be left blank while testing Telegram. Configure Telegram webhook and minute cron, then send `/id` privately to the bot to obtain your own ID. Run configure again and set that number; existing secrets can be kept by pressing Enter. Restart the Python application afterward.

```
python manage.py set-webhook
python manage.py check
```

The set-webhook command makes an outbound request to Telegram but does not discard pending updates. Do not run `bot.py` polling simultaneously with the webhook deployment.

## Cron

Use `* * * * *` (every minute). Command shape, with placeholders replaced using the paths visible in YOUR application details:

```
/ABSOLUTE/VIRTUALENV/bin/python /ABSOLUTE/APP/manage.py tick
```

Use absolute paths. It loads the private settings file; it does not rely on cPanel's web-only environment variables. The nonblocking file lock prevents overlapping tick processes. Keep cron emails or private logs enabled initially so failures are visible. Collection uses Asia/Yerevan internally, so the host's cron time zone does not change the 10:00 local threshold. Collection starts on the first tick at or after 10:00, not a guaranteed exact-time delivery.

## Verification and launch gate

Restart the cPanel Python application after installing source or changing settings. A GET request to the app root returns a minimal health response; it does not indicate valid credentials or successful monitoring. The webhook rejects requests without the secret header and deduplicates update IDs. No collection or automatic AI spending is enabled by default.

Test /start, /hy, /ru, /id, /stop, administrator approval and rejection using private test accounts. Failed inbox items remain `review` (or `processing` after a crash) for operator inspection; no blind retry of ambiguous sends is performed. Completed update payloads are cleared, but review payloads and subscriber IDs remain private in SQLite. Add backup, retention policy and operational monitoring before public launch.

CRITICAL: full ARLIS pagination/date coverage, content revision tracking, launch baseline, legal-text extraction and model accuracy remain unverified. The existing homepage adapter is insufficient for comprehensive legal monitoring. Keep `COLLECTION_ENABLED=false` until those tasks are completed and tested. This hosting adaptation does not resolve source completeness.

When validated, the collection flag must be enabled in the private settings file for cron as well as any WSGI settings. The configure command preserves existing extra keys. Editing credentials or config should be done only privately in the hosting account.

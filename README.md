# Novasol LawBot — pre-launch prototype

Configured for @Novasol_lawbot. Not deployed or connected to Telegram.

## Agreed behaviour

- Anyone can subscribe in a private Telegram chat, choosing Armenian or Russian.
- Starting at 10:00 Asia/Yerevan each day, generate drafts for the administrator.
- Subscribers receive a selected-language alert only after the administrator approves both translations.
- Late approval means later delivery; 10:00 is the draft preparation start time, not a guaranteed subscriber delivery time.
- Business legislation: taxes, customs, imports/exports, employment, licensing and related regulation.
- Original ARLIS source link included. No unattended publication.

## Required configuration

Python 3.11 or newer, no third-party packages. Set variables from `.env.example` in the hosting provider's secret/environment settings; this program does not automatically read .env files. Never commit actual credentials.

1. TELEGRAM_BOT_TOKEN: the replacement BotFather token, entered privately in hosting.
2. ADMIN_CHAT_ID: the owner's numeric Telegram user ID, not the bot's ID. Obtain privately through Telegram's own facilities or a trusted ID tool. Once configured, /id in this bot shows the chat ID.
3. OPENAI_API_KEY: a separately configured API key with billing and a spending limit.
4. OPENAI_MODEL: a currently available model supporting Chat Completions JSON object output. Verify it in your API account; no model or price is assumed.
5. DATABASE_PATH: a SQLite file on a persistent mounted disk. Run exactly ONE instance.

Start with `python bot.py`. The process must remain online for subscriptions, approvals and the schedule to function. Choose an always-on worker host with a persistent volume. Deployment and any associated spending have not been initiated.

## Telegram commands

`/start` — choose language; `/hy` — subscribe Armenian; `/ru` — subscribe Russian; `/language` — show language choices; `/stop` — unsubscribe; `/id` — show private chat ID.

The administrator gets each bilingual draft with Approve and Reject buttons. Repeated button presses cannot publish the same draft again. Membership at approval time determines the delivery audience; later subscribers receive future alerts.

## Important launch limitations

THIS IS NOT A COMPLETE ARLIS MONITOR. The initial source adapter reads document links visible in configured listing pages; the default homepage exposes only a small recent selection and can miss publications. Pagination and complete date-based listing discovery must be implemented and verified against live ARLIS before launch. No claim of comprehensive coverage is made. It does not monitor the State Revenue Committee.

The adapter currently detects new document URLs, not edits at an existing URL. Homepage links to older codes can become initial drafts. A launch-date baseline and content-version monitoring remain required. No official ARLIS API or subscription is assumed.

AI receives the complete extracted page, including possible navigation, and may make mistakes. Long or unreadable documents stop ingestion rather than being silently truncated. Relevant changes can be missed by AI filtering. Source coverage and effective dates require human verification. Rejected drafts cannot be edited in Telegram yet; an editing workflow remains to be added.

Delivery uses conservative at-most-once attempts. Network failures and interrupted sends are retained in SQLite as `review` or `sending` and need operator inspection, rather than risking duplicate broadcasts. Error reporting is limited to redacted console events; add operational alerts and a dead-letter management interface before launch. Daily ingestion currently shares the polling loop, so large batches can temporarily delay Telegram replies. Scheduling is persistent, retries after errors and catches up after 10:00 on restart, but is not a precision scheduling guarantee.

## Before public launch

Validate full listing coverage, document extraction, model compatibility and translation quality. Run live smoke tests with only the owner's test subscription: source ingestion, bilingual drafts, approval, rejection, unauthorized approval, restart, unsubscribe and delivery failures. Add database backup, monitoring and a subscriber-facing privacy notice. Review hosting and API costs before provisioning.

No real token, user identifier or API key is included. The exposed historical token has not been used.

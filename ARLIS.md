# ARLIS source extraction — current verification stage

## Verified against public site HTML on 2026-11-01

- Recent links end in `/latest`. The original strict URL pattern missed them.
- Recent cards have the `act-card__title` class; permanent shortcuts to codes are excluded.
- The actual legal content is in `#act_body`; metadata in `act-info__item`.
- The "amends the following acts" tab contains explicit comparison URLs. Other history tabs must not be interpreted as old/new pairs.
- Example: publication 233019 explicitly pairs acts 202348 and 233036. Both complete bodies and eleven metadata fields per version were extracted; six changed paragraph groups were detected. This is a technical extraction example, not a tax-news recommendation or legal interpretation.
- The public site JavaScript calls `/hy/releases/{section}/files?page={page}` with its AJAX headers. The endpoint lists official PDF files, separate from the act HTML pages.

## Hosting test (no keys, no AI usage, no Telegram posts)

Upload `arlis_source.py` and `check_arlis.py` beside `bot.py` in `/home/novasol/novasol-lawbot`, then run:

```
/home/novasol/novasol-lawbot/check_arlis.py
```

The command reports recent cards, legal-body extraction, linked revision-pair comparisons and PDF inventory. It changes no configuration and does not initialize or modify the bot database. It can take several minutes because it requests source pages sequentially. All automatic collection must remain disabled.

After the hosting source check passes, replace `bot.py` with the new version too. It imports `arlis_source.py` only during collection, preserving Telegram operation when collection is disabled.

## Not ready for automatic daily launch

The homepage has only six recent cards, which is NOT complete daily coverage. PDF extraction and a separate source ledger are now implemented, but PDFs are not matched to act HTML or converted into drafts yet. No State Revenue Committee feed is implemented. Archive/date-based discovery, automatic source scheduling, retry/backoff and spend guard remain required. Therefore KEEP `COLLECTION_ENABLED=false`.

Explicit comparisons support source-based before/after extraction. When a document lacks an explicit pair the summary must say the comparison is not established. If too many pairs or evidence exceeding the input size limit are found, ingestion stops rather than silently omitting evidence. Full titles may change, so identity relies on the site's explicit pairing rather than title equality. Commencement of individual provisions still requires source reading; metadata alone does not establish it.

The updated summary prompt requests Armenian sections about the change, before/after wording, affected parties, commencement and practical steps, and appends original source and revision links. This pipeline has not been validated with a successful live AI request; earlier API testing returned 429 with a zero balance.

Do not claim that the bot monitors every new legal act or that analysis is verified until the remaining source-coverage and model checks pass.

## PDF extraction and source ledger

Upload `requirements.txt`, `pdf_sources.py`, `check_pdf.py`, and `source_jobs.py` beside the existing `arlis_source.py` and `hosting.py`. Add `requirements.txt` to the Python application's configuration files and use cPanel's **Run pip install**. Run:

```
/home/novasol/novasol-lawbot/check_pdf.py
```

This downloads ONE official PDF and reports text extraction quality, without database writes, AI or Telegram requests. A live one-page correction publication was successfully extracted locally on 2026-11-01. One successful sample does not establish quality for all PDFs. Scanned pages, bad character encoding, encryption and size/page limits are sent to manual review; no OCR is implemented. Text quality heuristics cannot guarantee legal accuracy.

The following explicit commands maintain `.private/sources.sqlite3`, separately from the bot database:

```
/home/novasol/novasol-lawbot/source_jobs.py baseline
/home/novasol/novasol-lawbot/source_jobs.py scan
/home/novasol/novasol-lawbot/source_jobs.py extract
/home/novasol/novasol-lawbot/source_jobs.py status
```

Run `baseline` ONCE to mark current records as pre-existing, then `scan` for later discoveries. A second baseline is rejected to prevent hiding new publications. All requested section inventories must succeed before a scan commits. `extract` handles at most three pending PDFs per invocation, including baseline documents; it stores text, SHA-256, page count, review flags and embedded official links. Repeated inventory records and identical versions are deduplicated. Errors remain in the ledger for review; there is no automatic retry yet. No command generates drafts or publishes messages.

Current scope is only rolling weekly lists for sections 11, 15 and 16. Documents that disappear between scans can be missed; other categories, historical gaps and replacements at an already processed URL are not automatically checked. Baseline flags and stored versions prepare later integration but are not wired to the publishing pipeline. Do not add these commands to cron yet.


## HTML-first staging

HTML is the primary source format. PDF extraction is optional and is not needed by the bot's existing HTML collection or the new `check_html.py` and `html_sources.py` tools. All publishing remains subject to administrator approval.

Upload `check_html.py` and `html_sources.py` alongside the existing `arlis_source.py`. Run `/home/novasol/novasol-lawbot/check_html.py` to inspect up to three homepage cards without PDF, AI, Telegram or database writes. An optional official act URL tests one document, including its explicit comparison links. Missing pairs mean comparison is not established, not that nothing changed.

`html_sources.py baseline` explicitly saves existing homepage sources once; `scan` stores new or changed snapshots with status pending_review; `status` reports counts. The separate private HTML SQLite ledger deduplicates stable evidence hashes and rejects incomplete evidence. Source reads finish before the transaction commits. These snapshots are not yet wired to the draft queue. Do not schedule these staging commands or enable collection yet.

Discovery remains limited to recent homepage cards. Full date-based discovery and pagination are unresolved, so this change does not establish complete daily monitoring.


## PDF draft bridge (explicit commands, not scheduled)

Upload `pdf_drafts.py` alongside the existing bot, hosting and PDF source modules. No main bot or cron changes are required. The default command and `plan` inspect the saved source ledger without network calls; generation tracking tables are initialized in the bot database. The source ledger is opened read-only.

- `pdf_drafts.py plan`: counts eligible new extracted records, baseline exclusions, manual review exclusions and oversized sources. Current 29 baseline records are deliberately excluded. Ready=0 is expected until new documents have been discovered AND extracted.
- `pdf_drafts.py generate`: explicitly opts into at most ONE paid AI call. A maximum of three reservations per Yerevan day applies to this PDF bridge only (not the older HTML collector or unrelated API use). Complete source text plus title must fit 60,000 characters; no silent truncation. Failed/interrupted requests remain reserved and require operator review; no automatic paid retries.
- `pdf_drafts.py notify`: sends pending drafts to the configured administrator using the existing approval workflow. It does not publish directly to the channel. Administrator approval queues publication for the existing minute cron.
- `pdf_drafts.py status`: reports generation statuses and saved error classes without credentials.

Generation selects only records with is_baseline=0 and both latest version and record status extracted. Draft fingerprints combine source URL and PDF hash. Summaries are Armenian, append the verified PDF source URL and explicitly state that comparison to the previous edition is not established. This PDF-only bridge cannot substantiate before/after analysis. It does not match PDFs to official revision pairs yet. Relevance and legal interpretation still require human review. No successful live generation has been validated; prior OpenAI tests returned 429. Tests use mock generation and no paid requests.

Do not enable COLLECTION_ENABLED or add generation to cron yet. Discovery remains limited to the configured rolling lists; model quality, completeness, source-to-revision matching and operations/retry handling still need validation.

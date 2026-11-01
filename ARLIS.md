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

The homepage has only six recent cards, which is NOT complete daily coverage. Weekly PDF inventory is counted but PDFs are not extracted or matched to act HTML yet. No State Revenue Committee feed is implemented. Archive/date-based discovery, startup baseline, durable pending-source queue, retry/backoff and spend guard remain required. Therefore KEEP `COLLECTION_ENABLED=false`.

Explicit comparisons support source-based before/after extraction. When a document lacks an explicit pair the summary must say the comparison is not established. If too many pairs or evidence exceeding the input size limit are found, ingestion stops rather than silently omitting evidence. Full titles may change, so identity relies on the site's explicit pairing rather than title equality. Commencement of individual provisions still requires source reading; metadata alone does not establish it.

The updated summary prompt requests Armenian sections about the change, before/after wording, affected parties, commencement and practical steps, and appends original source and revision links. This pipeline has not been validated with a successful live AI request; earlier API testing returned 429 with a zero balance.

Do not claim that the bot monitors every new legal act or that analysis is verified until the remaining source-coverage and model checks pass.

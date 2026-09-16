# Grocery Spend Lab

Grocery Spend Lab is a local-first toolkit for turning itemized retailer
receipts into auditable spending tables and clear charts. It includes a visible
browser exporter for Harris Teeter and a retailer-agnostic analyzer for the
normalized JSON schema in [`docs/input-schema.md`](docs/input-schema.md).

The project measures category mix, provider-recorded markdown incidence,
delivery fees and tips, basket cadence, exact-UPC price observations, brand
identification, explicit product attributes, and milk/egg purchase consistency.
It does not claim that a markdown was a good deal, assign objective food quality,
or estimate market inflation.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
npm install
```

## Export Harris Teeter history

The exporter launches a visible Brave window with a dedicated browser profile.
Sign in yourself, then leave the purchase-history page open while it indexes and
exports receipts.

```bash
node bin/harris-teeter-export.js \
  --output exports/ht-2026-09-16 \
  --account household-1 \
  --start 2026-01-01
```

Set `BRAVE_PATH` or pass `--browser-path` for another Chromium executable. The
exporter writes normalized JSON/CSV plus provider response bodies for parser
auditability. It does not write credentials, cookies, or request headers.

## Analyze an export

```bash
grocery-spend \
  --orders exports/ht-2026-09-16/orders.json \
  --items exports/ht-2026-09-16/items.json \
  --output outputs/analysis-2026-09-16 \
  --merchant "Harris Teeter" \
  --account-label "household loyalty account" \
  --event-date 2026-07-04 \
  --event-label "Move"
```

The output directory must be new. It contains an analysis summary, auditable
CSV tables, eight PNG charts, and reconciliation exceptions. Try the included
synthetic data without exposing household information:

```bash
grocery-spend --orders examples/orders.json --items examples/items.json \
  --output outputs/example --merchant "Example Market"
```

## Interpretation limits

- Coverage is one retailer export, not total household grocery spending.
- Categories and brand types are deterministic text rules. `Brand unclear`
  stays separate instead of being guessed.
- Savings are labels supplied by the retailer. The tool measures incidence and
  dollars, not deal effectiveness.
- Price charts compare exact UPCs. They describe selected items and do not form
  an inflation index.
- Event windows are descriptive; channel, season, store, household needs, and
  incomplete coverage can explain apparent changes.

## License

MIT

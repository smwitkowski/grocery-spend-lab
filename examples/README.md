# Synthetic grocery history

`orders.json` and `items.json` contain a deterministic, entirely fictional
household history used by the tests and documentation. No row is derived from a
real receipt or retailer account.

The fixture covers a full year and intentionally varies shopping channel,
basket size, categories, quantities, stores, delivery costs, retailer-recorded
markdowns, missed items, and repeat-product prices. Descriptions are synthetic
combinations designed to exercise the classification rules; none were copied
from receipts. UPC-shaped identifiers are synthetic test values.

Regenerate both files from the repository root:

```bash
python scripts/generate_synthetic_examples.py
```

The default random seed is fixed so reviews and documentation images remain
reproducible. Pass `--seed` only when deliberately refreshing the fixture.

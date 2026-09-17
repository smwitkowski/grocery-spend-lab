# CLI workflow and recovery

## Discovery

```bash
grocery-spend capabilities
grocery-spend schema --name command-result
grocery-spend --version
```

Successful commands emit one JSON object to stdout. Progress and human-readable diagnostics belong on stderr.

## Validate and analyze

```bash
grocery-spend validate --orders "$ORDERS" --items "$ITEMS"
grocery-spend analyze --orders "$ORDERS" --items "$ITEMS" --output "$NEW_OUTPUT" \
  --merchant "Harris Teeter" --account-label "household account"
```

The analysis destination must not exist. The tool builds in an adjacent temporary directory and publishes the requested path only after writing the manifest.

## Exit codes

| Code | Meaning | Response |
|---:|---|---|
| 0 | Completed, possibly with data warnings | Inspect `status`, `warnings`, and artifacts |
| 1 | Unexpected execution failure | Preserve stderr and report the failing command |
| 2 | Invalid CLI usage | Correct arguments using `--help` |
| 3 | Invalid input data | Fix the reported structural or relational errors |
| 4 | Browser authentication or user action required | Ask the user to sign in visibly |
| 5 | Output conflict or filesystem failure | Select a new destination; do not delete an existing run automatically |

## Harris Teeter collection

```bash
npx --no-install grocery-spend-export-harris-teeter \
  --output "$NEW_EXPORT" --account household-1 --non-interactive
```

If this returns `AUTH_REQUIRED`, rerun without `--non-interactive` while the user is present. Add `--save-raw-responses` only when parser auditability is needed; the raw payloads may contain partial payment details.

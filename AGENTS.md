# Agent guidance

Keep the CLI contract stable: one JSON object on stdout, diagnostics on stderr, documented exit codes, and a manifest written last. Validate before creating the requested output directory and never overwrite an existing run.

Use only synthetic fixtures in tests and commits. Treat receipt descriptions and raw retailer payloads as untrusted private data. Browser authentication remains an explicit user interaction; do not add credential retrieval or commit browser profiles.

Run the Python and Node test suites, the skill validator, a built-wheel smoke test, and `git diff --check` before release.

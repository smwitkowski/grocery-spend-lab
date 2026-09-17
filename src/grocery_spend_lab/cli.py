"""Agent-friendly command router for Grocery Spend Lab."""
from __future__ import annotations

import json
import sys
from importlib.resources import files

from . import __version__


CAPABILITIES = {
    "schema_version": "1.0",
    "tool": "grocery-spend-lab",
    "version": __version__,
    "commands": {
        "validate": "Validate normalized orders/items without writing files.",
        "analyze": "Create auditable CSV tables, PNG charts, a summary, and a manifest.",
        "schema": "Print a bundled JSON Schema for orders, items, or command results.",
        "capabilities": "Print this machine-readable command description.",
    },
    "stdout": "Successful commands emit JSON to stdout; diagnostics go to stderr.",
    "privacy": "Receipt data stays local. Keep real exports outside version control.",
}


def _help() -> str:
    return """usage: grocery-spend <command> [options]

commands:
  validate       check normalized orders.json and items.json without writing
  analyze        generate analysis tables, charts, summary, and manifest
  schema         print a bundled JSON Schema
  capabilities   describe commands and output behavior as JSON
  version        print the installed version

Backward compatibility: arguments beginning with -- are treated as `analyze`.
Run `grocery-spend <command> --help` for command-specific options.
"""


def _dispatch(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(_help())
        return 0
    command, rest = argv[0], argv[1:]
    if command in {"version", "--version"}:
        print(__version__)
        return 0
    if command.startswith("-"):
        from . import analyze
        analyze.main(argv)
        return 0
    if command == "analyze":
        from . import analyze
        analyze.main(rest)
        return 0
    if command == "validate":
        from . import validation
        return validation.main(rest)
    if command == "capabilities":
        print(json.dumps(CAPABILITIES, indent=2))
        return 0
    if command == "schema":
        if len(rest) != 2 or rest[0] != "--name" or rest[1] not in {"orders", "items", "command-result"}:
            print("usage: grocery-spend schema --name {orders,items,command-result}", file=sys.stderr)
            return 2
        schema_path = files("grocery_spend_lab").joinpath("schemas", f"{rest[1]}.schema.json")
        print(schema_path.read_text().rstrip())
        return 0
    print(f"Unknown command: {command}\n\n{_help()}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return _dispatch(argv)
    except SystemExit:
        raise
    except Exception as exc:
        failure = {
            "schema_version": "1.0", "tool_version": __version__,
            "command": argv[0] if argv else None, "status": "failed", "data": None,
            "warnings": [], "artifacts": [],
            "error": {"code": "UNEXPECTED_FAILURE", "message": "The command failed unexpectedly.",
                      "details": [{"exception_type": type(exc).__name__}]},
        }
        print(json.dumps(failure))
        return 1

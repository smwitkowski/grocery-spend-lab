# Agent interface

Grocery Spend Lab exposes a small, versioned interface for coding agents:

- `capabilities` for discovery.
- `schema` for normalized inputs and command results.
- `validate` for read-only preflight.
- `analyze` for artifact generation.
- `manifest.json` as the completion record.
- A portable Agent Skill in `skills/grocery-spend-lab`.

The command envelope separates execution status from data warnings. It keeps aggregate results and artifact pointers on stdout instead of emitting receipt rows. Analysis runs offline. Browser collection is separate because it has a different runtime and may require visible user authentication.

The structure follows the [Agent Skills specification](https://agentskills.io/specification). The schema-discovery approach was informed by the [Google Workspace CLI](https://github.com/googleworkspace/cli); the implementation stays static because this project has only three contracts. Exit behavior follows the same explicit, scriptable pattern documented by [GitHub CLI](https://cli.github.com/manual/gh_help_exit-codes), without copying its numeric meanings.

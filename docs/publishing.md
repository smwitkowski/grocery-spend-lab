# Publishing Grocery Spend Lab

The first public distribution should contain the Python analysis CLI. Keep the
Harris Teeter Node exporter available from the source repository until it has an
independent package, installation contract, and browser compatibility matrix.

## Distribution contract

| Surface | Purpose | User command |
|---|---|---|
| PyPI | Canonical CLI package | `uvx grocery-spend-lab` or `pipx install grocery-spend-lab` |
| GitHub Releases | Version notes and source/package artifacts | Download or inspect a tagged release |
| Git repository | Contributor checkout, Agent Skill, browser exporter | Clone and install development dependencies |

PyPA recommends console-script entry points and isolated CLI installation with
pipx. Astral documents the equivalent `uvx` and `uv tool install` workflows.

## One-time PyPI setup

1. Create or sign in to the owner's PyPI account and enable two-factor authentication.
2. Register a pending Trusted Publisher for:
   - PyPI project: `grocery-spend-lab`
   - GitHub owner: `smwitkowski`
   - Repository: `grocery-spend-lab`
   - Workflow: `publish.yml`
   - Environment: `pypi`
3. In GitHub, create the `pypi` environment and require approval before deployment.

The exact PyPI name returned HTTP 404 on 2026-09-17, but availability is only
confirmed when the first release successfully claims it.

## Release procedure

1. Update the version in `pyproject.toml` and `src/grocery_spend_lab/__init__.py`.
2. Add the release notes to `CHANGELOG.md`.
3. Run the full tests and build checks locally.
4. Commit and push the release preparation; wait for CI to pass.
5. Create and publish a GitHub release whose tag matches the package version,
   such as `v0.2.0`.
6. The release workflow builds one sdist and one wheel, checks their metadata,
   and publishes those exact artifacts through PyPI Trusted Publishing.
7. Verify the PyPI provenance and test from outside the checkout:

```bash
uvx grocery-spend-lab --version
pipx run grocery-spend-lab --version
```

PyPI's official publishing action creates PEP 740 attestations by default. The
workflow receives only `id-token: write`; it stores no PyPI token.

## Primary references

- [Creating and packaging command-line tools](https://packaging.python.org/en/latest/guides/creating-command-line-tools/)
- [Writing `pyproject.toml`](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Publishing from GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [PyPI digital attestations](https://docs.pypi.org/attestations/producing-attestations/)
- [pipx](https://pipx.pypa.io/stable/)
- [uv tools](https://docs.astral.sh/uv/guides/tools/)
- [Agent Skills specification](https://agentskills.io/specification)

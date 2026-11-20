# 0.1.0 Alpha release checks

The reference environment is Windows, Blender 5.2.0 LTS, Python 3.12, and MCP Python SDK 1.28.1. The manifest declares a minimum of Blender 4.5.0. Other Blender versions and platforms need compatibility testing.

## Reproduce

1. Run the Python checks and Ruff commands in the README.
2. Run `tests/blender_integration.py` in a fresh Blender background process with an empty export folder.
3. Run `python tests/e2e.py --blender /path/to/blender`.
4. Run the same command with `--live` in a graphical session to exercise Blender's timer, the sidebar operator, and a 64×64 Workbench PNG render.
5. Build the archives with `python scripts/package.py`. Validate the extension with `blender --command extension validate dist/kitquen_forge-0.1.0.zip`.

The end-to-end harness uses the official MCP SDK client. Codex and Claude Code setup commands are documented separately. Those clients require their own session and approval configuration.

## Command-size measurement

The `o200k_base` tokenizer counted 62 tokens for the Blender Python sample, 40 for readable Kitlean 3D, and 20 for compact Kitlean 3D. Each sample creates, resizes, and positions one cube. The measurement covers command text alone. Tool descriptions, context, responses, retry rates, and complete agent workflows are outside this microbenchmark.

Run `python -m pip install ".[bench]"` and `python benchmarks/compare.py` to reproduce.

## Before public publication

- Confirm the GitHub owner and obtain approval to publish the repository and release.
- Record the release commit and attach the validated Blender extension.
- Confirm repository contact details. Add funding metadata only when a maintainer provides an account or URL.

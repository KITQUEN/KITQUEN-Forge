# KITQUEN Forge

**AI-First 3D Modeling for Blender**

An open-source toolkit that helps AI agents create, edit, animate, and export 3D scenes using a compact Python-powered language and MCP.

## 0.1 Alpha

Forge adds a native **Forge** sidebar to Blender. Start a session for an active scene, then connect Codex, Claude Code, or another MCP client. The client launches a local stdio server. Blender processes its commands on the main thread through a temporary filesystem queue. Forge has no hosted components, service credentials, or bundled AI model.

- Model with six primitives, transformations, duplication, parenting, and a cylindrical Boolean cut.
- Set materials, add cameras and lights, and animate location, rotation, or scale with Blender keyframes.
- Inspect one object or a page of objects. Query mesh topology, materials, animation, or hierarchy.
- Roll back failed modeling batches. Undo and redo successful Forge batches during the same connection.
- Export STL, OBJ, GLB, or a BLEND copy. Queue a PNG still render and retrieve its result.
- Edit existing Forge objects by alias or persistent ID.

## Start here

1. Install the extension ZIP in **Edit → Preferences → Get Extensions → Install from Disk**. Enable **KITQUEN Forge** if Blender does not enable it automatically.
2. In the 3D View, press **N** and open **Forge**. Choose an existing export folder if needed. Click **Start Connection** and **Copy Session Path**.
3. At the extracted source directory, run `python -m pip install .` using Python 3.11 or later. Register the server and optional agent skill using the [AI quickstart](docs/AI_QUICKSTART.md).
4. Ask the agent to call `forge_status`, then use the returned scene with `forge_execute`.

The extension manifest targets Blender 4.5+. See [release checks](docs/RELEASE.md) for environments actually exercised.

```text
+cube/base size=4,4,2
+hole/base d=1
@color/base #FF6600
+torus/ring size=2,2,0.5
@pos/ring 0,0,1.3
~rotate/ring axis=z deg=360 frames=1:120
!timeline 1:120
```

See the [versioned syntax](skills/kitquen-forge/references/syntax.md) and [working example](examples/demo.kln3d).

## Project map

| Path | Contents |
| --- | --- |
| `kitquen_forge/language` | Python parser, validated IR, compact and readable serializers |
| `kitquen_forge` | Blender extension, interpreter, journal, queue, export |
| `forge_mcp` | Official Python MCP SDK integration |
| `docs`, `skills/kitquen-forge` | Setup guide and installable Agent Skill |
| `examples`, `benchmarks`, `tests` | Example script, token microbenchmark, and automated checks |

## Tests and packaging

```sh
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
blender -b --factory-startup --python-exit-code 1 --python tests/blender_integration.py -- /path/to/empty/output
python tests/e2e.py --blender /path/to/blender
python scripts/package.py
```

The Python checks also run with `python -m unittest discover -s tests -v` if the MCP SDK is installed. On Windows, pass the full path to `blender.exe`. The Blender integration test expects an empty output folder each time.

## Limits and roadmap

Alpha edits apply to Forge-managed objects. The local queue is for agents running under your trusted account. History is session-scoped, bounded to 20 batches, and cleared when a connection stops. Native Blender undo or loading a different file disconnects Forge. Files written by export or rendering sit outside the modeling undo journal. STL carries mesh geometry. OBJ adds applicable material information. GLB carries supported materials and animation. A BLEND copy can reference external assets that must be moved separately.

Render jobs run on Blender's main thread and may temporarily block the interface or status polling. The current service retains the latest render job. Advanced mesh editing, procedural primitives, richer animation and constraints, cancellation, and broader OS and Blender coverage belong to later milestones. See [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md).

The optional [token microbenchmark](benchmarks/compare.py) measures command text with a real tokenizer. An end-to-end benchmark across agents and tasks remains in the roadmap.

## License and support

Original source is [MIT licensed](LICENSE). The Blender extension can also be distributed under GPL-3.0-or-later as indicated in its extension manifest. The stdio server uses the MIT-licensed MCP Python SDK as a separately installed dependency. Blender is a separate application distributed under its own GPL license.

Forge is free to use. Contributions and issue reports are welcome. A maintainer can add voluntary donation links once a real account URL is available.

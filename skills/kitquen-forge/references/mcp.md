# MCP and Blender

| Tool | Purpose |
| --- | --- |
| `forge_status` | Check transport and get the approved scene |
| `forge_execute` | Execute a Kitlean script in the approved scene |
| `forge_validate` | Validate or convert syntax before execution |
| `forge_inspect` | Inspect an ID, alias, selection, or page of managed objects |
| `forge_scene_summary` | Check object count and timeline |
| `forge_help` | Retrieve one topic |
| `forge_undo`, `forge_redo` | Navigate Forge's session history |
| `forge_export` | Write one model or project copy |
| `forge_render` | Queue and check a PNG still |

The stdio server runs as `python -m forge_mcp --session "/absolute/path/session.json"`. Copy the session path from Blender. Start the bridge for the intended scene and use Object Mode for mutations. Inspect filters include basic, hierarchy, geometry, materials, animation, and all. Use an `id:` prefix to disambiguate aliases such as `managed`.

---
name: kitquen-forge
description: Use KITQUEN Forge MCP to create, edit, animate, inspect, render, or export assets in a locally approved Blender scene using compact Kitlean 3D.
---

# KITQUEN Forge Skill

1. Call `forge_status`. Use the returned `scene` in scene tools. If offline or inactive, ask the operator to start Forge or activate the scene shown by status.
2. Inspect only the relevant aliases or IDs. Batch related changes in one `forge_execute` call. Retain the returned IDs when editing the same asset later.
3. Validate unfamiliar syntax with `forge_validate` and use short compact commands. Inspect the result after the batch. If a timeout occurs, inspect before retrying.
4. Use a simple filename with `forge_export` or `forge_render`. Writing requires a folder already approved in the Blender panel.

- [Syntax](references/syntax.md) for grammar and conversion.
- [Modeling](references/modeling.md), [animation](references/animation.md), and [materials](references/materials.md) for command details.
- [Rendering and export](references/rendering.md) for file or render requests.
- [Tools](references/mcp.md), [errors](references/errors.md), and [optimization](references/optimization.md) for connection, recovery, and call size.
- [Example](examples/tile.kln3d) for a printable tile with a cutout.

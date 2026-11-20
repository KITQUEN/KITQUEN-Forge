# Rendering and export

Create a camera with `+camera/cam`, position it using `@pos/cam`, aim using `@rot/cam`, and make it active with `!camera/cam`. An unrotated Blender camera points down local Z. Existing active cameras also work for renders.

Call `forge_render` with `scene`, `name: "preview.png"`, and optional width, height, and engine (workbench, eevee, or cycles). Poll again with `scene` and the returned `job`. The current render can block Blender while it runs, so wait before polling and inspect status after a timeout.

`forge_export` accepts STL, OBJ, GLB, or BLEND. Set `selected: true` to export the selection with STL, OBJ, or GLB. BLEND writes a project copy and preserves relative link text. GLB supports applicable animation and materials. Inline `!export/stl model.stl` must be the final line. Forge rejects traversal, absolute paths, and overwrites. Agent undo acts on the scene. Removing generated files is a separate operation.

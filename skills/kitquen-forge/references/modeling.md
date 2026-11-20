# Modeling

Use `+cube/base size=4,4,2` and the same pattern with sphere, cylinder, cone, plane, and torus. Sizes are Blender units. Planes ignore the depth component. Primitives begin at world origin. `@size` sets dimensions on an unrotated mesh. `@scale` sets absolute scale factors. `@rot` accepts Euler degrees and `@pos` sets local position.

`+hole/base d=1 at=0,0,0` cuts a cylinder along world Z, centered on the target's bounding box plus optional offset. Run cuts on solid Forge meshes without existing modifiers. Use the geometry filter in `forge_inspect` to check the topology before export.

`+copy/base as=part` copies an object with a new stable ID. `@parent/part base` assigns a parent while retaining local transforms. `-/part` removes a Forge object from the scene. Objects with children, shared collection links, or the active camera are protected. Groups of mutations can be undone as a batch.

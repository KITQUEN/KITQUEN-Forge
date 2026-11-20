# Security and scene control

Start a Forge connection only for a trusted local agent. The filesystem queue is created in the user's temporary directory. Filesystem access to that directory grants connection access. Keep the session path and its directory private. The MCP client connection uses stdio. Forge opens no listening network port.

Forge parses Kitlean 3D against a fixed operation schema. Mutating scene requests must name the scene approved at startup and run while it is active in Object Mode. Object references resolve only to Forge-managed objects. Export names are restricted to flat filenames in the approved folder. The host writes a local operation log in the temporary session folder.

Use a separate copy of valuable projects when evaluating the alpha. A render or export may outlast the client timeout. Check the scene and output directory before retrying. Forge history can conflict with manual changes to the same objects. Native undo disconnects the bridge to invalidate stale references.

Before publication, configure a private reporting channel in the repository. Reports should include the affected version, a minimal reproduction, and the impact. Avoid sending project files or session descriptors in public issues.

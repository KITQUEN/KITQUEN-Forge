# Errors

Responses have `ok`, and failures include a source line when tied to a command. Line zero means request, scene, or transport scope. `INVALID_COMMAND` identifies syntax issues. `INVALID_TARGET` means the alias or ID could not be resolved. `AMBIGUOUS_TARGET` can occur after manually duplicating a Forge object's custom properties. Use Forge duplication to mint a new ID.

`WRONG_SCENE` and `OBJECT_MODE_REQUIRED` require checking Blender's active view. `OFFLINE` calls for the current session path. `FILE_EXISTS` requires a fresh filename. After `TIMEOUT`, inspect before retrying because Blender may have begun working. The local session log is next to the Blender-generated descriptor.

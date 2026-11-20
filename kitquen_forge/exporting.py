"""Blender exports scoped to one explicitly approved folder."""

import os
import shutil
import tempfile
from pathlib import Path, PureWindowsPath

import bpy

from .engine import require_finished
from .language import ForgeError

FORMATS = {"stl", "obj", "glb", "blend", "png"}
RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)),
}


def safe_name(fmt, name):
    if (
        not isinstance(fmt, str)
        or fmt not in FORMATS
        or not isinstance(name, str)
        or not 1 <= len(name) <= 120
        or name.startswith(".")
        or any(c in name for c in '/\\:<>"|?*')
        or any(ord(char) < 32 for char in name)
        or PureWindowsPath(name).stem.split(".")[0].strip().upper() in RESERVED
        or Path(name).suffix.lower() != f".{fmt}"
    ):
        raise ForgeError("INVALID_PATH", f"use a simple .{fmt} filename")
    return name


def publish(staging, root):
    written = []
    try:
        for path in sorted(staging.iterdir()):
            destination = root / path.name
            try:
                with destination.open("xb") as target:
                    written.append(destination)
                    with path.open("rb") as stream:
                        shutil.copyfileobj(stream, target)
            except FileExistsError as exc:
                raise ForgeError("FILE_EXISTS", path.name) from exc
    except Exception:
        for destination in written:
            destination.unlink(missing_ok=True)
        raise
    return [path.name for path in written]


def export(root, fmt, name, selected):
    if fmt == "png":
        raise ForgeError("INVALID_FORMAT", "use forge_render for PNG")
    safe_name(fmt, name)
    if not root or not root.is_dir():
        raise ForgeError("EXPORT_ROOT_REQUIRED", "choose an existing export folder in Blender")
    if os.path.lexists(root / name):
        raise ForgeError("FILE_EXISTS", name)
    if selected and fmt == "blend":
        raise ForgeError("INVALID_SELECTION", "BLEND exports a copy of the entire project")
    if selected and not bpy.context.selected_objects:
        raise ForgeError("EMPTY_SELECTION", "select objects in Blender")
    with tempfile.TemporaryDirectory(prefix=".forge-", dir=root) as folder:
        staging = Path(folder)
        path = str(staging / name)
        if fmt == "stl":
            result = bpy.ops.wm.stl_export(filepath=path, export_selected_objects=selected)
        elif fmt == "obj":
            result = bpy.ops.wm.obj_export(filepath=path, export_selected_objects=selected)
        elif fmt == "glb":
            result = bpy.ops.export_scene.gltf(
                filepath=path,
                export_format="GLB",
                use_selection=selected,
                use_active_scene=True,
            )
        else:
            result = bpy.ops.wm.save_as_mainfile(filepath=path, copy=True, relative_remap=False)
        require_finished(result)
        if not (staging / name).is_file():
            raise ForgeError("EXPORT_FAILED", name)
        files = publish(staging, root)
    return {"ok": True, "message": f"OK {len(files)}", "files": files}

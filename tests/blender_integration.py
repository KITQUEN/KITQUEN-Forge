"""Run with blender -b --factory-startup --python-exit-code 1 --python this-file."""

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import kitquen_forge  # noqa: E402
from kitquen_forge.engine import ID  # noqa: E402
from kitquen_forge.exporting import safe_name  # noqa: E402
from kitquen_forge.language import ForgeError  # noqa: E402
from kitquen_forge.ui import service  # noqa: E402

kitquen_forge.register()
scene = bpy.context.scene
root = Path(sys.argv[-1]).resolve() if "--" in sys.argv else Path.cwd() / "build" / "integration"
root.mkdir(exist_ok=True, parents=True)
descriptor = service.start(scene, str(root), parent=root)
script = """
+cube/base size=4,4,2
+hole/base d=1
@color/base #FF6600
+copy/base as=copy
@pos/copy 5,0,0
~move/copy from=5,0,0 to=6,0,0 frames=1:24
~rotate/copy axis=z deg=90 frames=1:24
!timeline 1:24
"""
args = {"scene": scene.name}
result = service.dispatch("execute", {**args, "script": script})
assert result["ok"] and result["count"] == 8
base = service.engine.find(scene, "base")
copy = service.engine.find(scene, "copy")
stable = copy[ID]
assert len(base.data.vertices) > 8
assert len(base.data.materials) == 1
assert copy.animation_data.action.frame_range[:] == (1, 24)
scene.frame_set(24)
assert math.isclose(copy.location.x, 6)
assert math.isclose(copy.rotation_euler.z, math.pi / 2, rel_tol=1e-6)
scene.frame_set(1)
assert math.isclose(copy.location.x, 5)
assert tuple(base.dimensions) == (4, 4, 2)
for op in ("undo", "redo"):
    assert service.dispatch(op, args)["ok"]
    if op == "undo":
        assert "base" not in scene.objects and "copy" not in scene.objects
assert service.engine.find(scene, stable) == copy
for script in ("+sphere/bad\n@pos/missing 1,2,3", "@pos/base 9,0,0\n@parent/base base"):
    try:
        service.dispatch("execute", {**args, "script": script})
    except ForgeError as exc:
        assert exc.line == 2
    else:
        raise AssertionError("Expected rollback")
assert "bad" not in scene.objects and not any(base.location)

geometry = service.dispatch(
    "execute",
    {
        **args,
        "script": """
+sphere/orb size=2
+cylinder/column size=2,2,4
+cone/peak size=2,2,3
+plane/floor size=6,6,1
+torus/ring size=2,2,0.5
+light/key type=point power=500
@energy/key 800
+camera/forge_camera
@pos/forge_camera 0,0,10
!camera/forge_camera
""",
    },
)
assert geometry["count"] == 10 and len(geometry["ids"]) == 7
assert service.engine.find(scene, "key").data.energy == 800
assert scene.camera == service.engine.find(scene, "forge_camera")
assert service.dispatch("undo", args)["ok"]
assert scene.camera.name == "Camera"
for name in ("../escape.stl", "C:\\escape.stl", "NUL.stl", "test.stl.txt"):
    try:
        safe_name("stl", name)
    except ForgeError:
        pass
    else:
        raise AssertionError(name)
for fmt in ("stl", "obj", "glb", "blend"):
    result = service.dispatch("export", {**args, "format": fmt, "name": f"model.{fmt}"})
    assert result["ok"] and (root / f"model.{fmt}").stat().st_size > 32
try:
    service.dispatch("export", {**args, "format": "stl", "name": "model.stl"})
except ForgeError as exc:
    assert exc.code == "FILE_EXISTS"
else:
    raise AssertionError("Expected overwrite rejection")
kitquen_forge.unregister()
assert not descriptor.exists()
print("FORGE BLENDER INTEGRATION PASSED")

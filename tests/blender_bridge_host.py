"""Temporary Blender process for the end-to-end MCP test."""

import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kitquen_forge.exchange import write_json  # noqa: E402
from kitquen_forge.service import Service  # noqa: E402

root = Path(sys.argv[-1])
if not bpy.app.background:
    import kitquen_forge
    from kitquen_forge.ui import service

    def start_ui_test():
        kitquen_forge.register()
        bpy.context.window_manager.forge_export_root = str(root)
        assert bpy.ops.forge.action(action="start") == {"FINISHED"}
        write_json(root / "ready.json", {"session": str(service.directory / "session.json")})
        return None

    def quit_when_done():
        if (root / "stop").exists():
            kitquen_forge.unregister()
            bpy.ops.wm.quit_blender()
            return None
        return 0.1

    bpy.app.timers.register(start_ui_test, first_interval=0.25)
    bpy.app.timers.register(quit_when_done, first_interval=0.5)

else:
    service = Service()
    session = service.start(bpy.context.scene, str(root), parent=root)
    write_json(root / "ready.json", {"session": str(session)})
    deadline = time.monotonic() + 120
    try:
        while not (root / "stop").exists() and time.monotonic() < deadline:
            service.tick()
            time.sleep(0.03)
    finally:
        service.stop()

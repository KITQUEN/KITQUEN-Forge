"""Native Blender controls for the local Forge bridge."""

import bpy
from bpy.app.handlers import persistent
from bpy.props import EnumProperty, StringProperty

from .language import ForgeError
from .service import Service

service = Service()


def tick():
    previous = service.last_request
    interval = service.tick()
    if previous == service.last_request:
        return interval
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return interval


@persistent
def stop_on_undo(_):
    service.stop()


@persistent
def stop_on_load(_):
    service.stop()


class FORGE_OT_action(bpy.types.Operator):
    bl_idname = "forge.action"
    bl_label = "Forge Action"

    action: EnumProperty(
        items=[
            (name, name.replace("_", " ").title(), "")
            for name in (
                "start",
                "stop",
                "copy",
                "undo",
                "redo",
                "validate",
                "stl",
                "obj",
                "glb",
                "support",
            )
        ]
    )

    def execute(self, context):
        scene = context.scene
        args = {"scene": scene.name}
        try:
            if self.action == "start":
                folder = context.window_manager.forge_export_root
                service.start(scene, bpy.path.abspath(folder) if folder else "")
                if not bpy.app.timers.is_registered(tick):
                    bpy.app.timers.register(tick)
            elif self.action == "stop":
                service.stop()
            elif self.action == "copy":
                if not service.directory:
                    raise ForgeError("OFFLINE", "start the connection first")
                context.window_manager.clipboard = str(service.directory / "session.json")
                self.report({"INFO"}, "Session file path copied")
            elif self.action == "support":
                self.report({"INFO"}, "Support Forge through contributions and issue reports")
            elif self.action == "validate":
                result = service.dispatch(
                    "inspect", {**args, "target": "selected", "detail": "geometry", "limit": 32}
                )
                meshes = [obj["mesh"] for obj in result["objects"] if "mesh" in obj]
                nonmanifold = sum(mesh["nonmanifold_edges"] for mesh in meshes)
                inconsistent = sum(mesh["inconsistent_edges"] for mesh in meshes)
                self.report(
                    {"INFO"},
                    f"Meshes {len(meshes)} | Non-manifold edges {nonmanifold} | "
                    f"Inconsistent edges {inconsistent}",
                )
            elif self.action in {"undo", "redo"}:
                result = service.dispatch(self.action, args)
                self.report({"INFO"}, result["message"])
            else:
                args.update(format=self.action, name=f"forge.{self.action}", selected=False)
                result = service.dispatch("export", args)
                self.report({"INFO"}, "Exported " + ", ".join(result["files"]))
        except (ForgeError, OSError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class FORGE_PT_sidebar(bpy.types.Panel):
    bl_label = "KITQUEN Forge"
    bl_idname = "FORGE_PT_sidebar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Forge"

    def draw(self, context):
        layout = self.layout
        running = bool(service.directory)
        box = layout.box()
        box.label(text="Connection")
        box.label(
            text="Bridge listening" if running else "Bridge stopped",
            icon="LINKED" if running else "UNLINKED",
        )
        folder_row = box.row()
        folder_row.enabled = not running
        folder_row.prop(context.window_manager, "forge_export_root")
        if running:
            box.operator("forge.action", text="Copy Session Path").action = "copy"
            box.operator("forge.action", text="Stop Connection").action = "stop"
            if service.last_request:
                box.label(text=f"Last agent: {service.agent}")
        else:
            box.operator("forge.action", text="Start Connection").action = "start"

        scene = layout.box()
        scene.label(text=f"Scene: {context.scene.name} ({len(context.scene.objects)})")
        scene.label(text=service.last[:48])
        if running and service.scene != context.scene:
            scene.label(text=f"Activate {service.scene.name}", icon="ERROR")
        operations = scene.column(align=True)
        operations.enabled = running and service.scene == context.scene
        operations.operator("forge.action", text="Undo Agent Action").action = "undo"
        operations.operator("forge.action", text="Redo Agent Action").action = "redo"
        operations.operator("forge.action", text="Check Selected Meshes").action = "validate"
        row = layout.row(align=True)
        row.enabled = bool(running and service.root and service.scene == context.scene)
        for fmt in ("stl", "obj", "glb"):
            row.operator("forge.action", text=fmt.upper()).action = fmt
        about_header, about = layout.panel("forge_about", default_closed=True)
        about_header.label(text="About")
        if about is not None:
            about.label(text="KITQUEN Forge 0.1 Alpha")
            about.operator("forge.action", text="Support Development").action = "support"


def register():
    bpy.utils.register_class(FORGE_OT_action)
    bpy.utils.register_class(FORGE_PT_sidebar)
    bpy.types.WindowManager.forge_export_root = StringProperty(
        name="Export Folder",
        subtype="DIR_PATH",
        description="Optional approved output directory",
    )
    bpy.app.handlers.undo_pre.append(stop_on_undo)
    bpy.app.handlers.redo_pre.append(stop_on_undo)
    bpy.app.handlers.load_pre.append(stop_on_load)


def unregister():
    service.stop()
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    bpy.app.handlers.undo_pre.remove(stop_on_undo)
    bpy.app.handlers.redo_pre.remove(stop_on_undo)
    bpy.app.handlers.load_pre.remove(stop_on_load)
    del bpy.types.WindowManager.forge_export_root
    bpy.utils.unregister_class(FORGE_PT_sidebar)
    bpy.utils.unregister_class(FORGE_OT_action)

"""KITQUEN Forge Blender extension."""

bl_info = {
    "name": "KITQUEN Forge",
    "author": "KITQUEN Forge contributors",
    "version": (0, 1, 0),
    "blender": (4, 5, 0),
    "location": "3D View > Sidebar > Forge",
    "category": "Object",
}


def register():
    from . import ui

    ui.register()


def unregister():
    from . import ui

    ui.unregister()

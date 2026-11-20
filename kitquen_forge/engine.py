"""Main-thread Blender interpreter. MCP never imports this module."""

import logging
import math
import uuid

import bpy
from mathutils import Vector

from .language import PRIMITIVES, ForgeError, parse

LOG = logging.getLogger(__name__)
ID = "kitquen_forge_id"
ALIAS = "kitquen_forge_alias"


class Journal:
    def __init__(self):
        self.steps = []

    def change(self, before, after):
        # Record before applying so a partially failed change is reversible.
        self.steps.append((before, after))
        after()

    def assign(self, obj, key, value):
        old = getattr(obj, key)
        if isinstance(old, Vector) or key == "rotation_euler":
            old = old.copy()
        self.change(lambda: setattr(obj, key, old), lambda: setattr(obj, key, value))

    def replay(self, reverse=False):
        applied = []
        steps = reversed(self.steps) if reverse else self.steps
        direction = 0 if reverse else 1
        try:
            for pair in steps:
                pair[direction]()
                applied.append(pair)
        except Exception:
            for pair in reversed(applied):
                try:
                    pair[1 - direction]()
                except Exception:
                    LOG.exception("History compensation failed")
            raise

    def rollback(self):
        for before, _ in reversed(self.steps):
            try:
                before()
            except Exception:
                LOG.exception("Batch rollback failed")


def rgb(hex_color):
    values = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return tuple(
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in values
    )


def require_finished(result):
    if "FINISHED" not in result:
        raise ForgeError("BLENDER_CANCELLED", "Blender cancelled the operation")


def object_info(obj, detail="basic"):
    data = {"id": obj.get(ID), "alias": obj.get(ALIAS), "name": obj.name, "type": obj.type}
    if detail in {"basic", "all"}:
        data.update(
            position=list(obj.location),
            dimensions=list(obj.dimensions),
            rotation=[math.degrees(item) for item in obj.rotation_euler],
            scale=list(obj.scale),
        )
    if detail in {"hierarchy", "all"}:
        data["parent"] = (obj.parent.get(ID) or obj.parent.name) if obj.parent else None
        data["children"] = [child.get(ID) or child.name for child in list(obj.children)[:64]]
    if detail in {"geometry", "all"} and obj.type == "MESH":
        import bmesh

        mesh = bmesh.new()
        try:
            mesh.from_mesh(obj.data)
            data["mesh"] = {
                "vertices": len(mesh.verts),
                "edges": len(mesh.edges),
                "faces": len(mesh.faces),
                "nonmanifold_edges": sum(not edge.is_manifold for edge in mesh.edges),
                "inconsistent_edges": sum(
                    edge.is_manifold and not edge.is_contiguous for edge in mesh.edges
                ),
            }
        finally:
            mesh.free()
    if detail in {"materials", "all"}:
        data["materials"] = [
            slot.material.name for slot in list(obj.material_slots)[:64] if slot.material
        ]
    if detail in {"animation", "all"}:
        action = obj.animation_data.action if obj.animation_data else None
        data["animation"] = (
            {"action": action.name, "frames": list(action.frame_range)} if action else None
        )
    return data


class Engine:
    def __init__(self):
        self.past = []
        self.future = []

    def clear_history(self):
        self.past.clear()
        self.future.clear()

    def find(self, scene, target):
        matches = [obj for obj in scene.objects if target in (obj.get(ID), obj.get(ALIAS))]
        if len(matches) != 1:
            raise ForgeError("AMBIGUOUS_TARGET" if matches else "INVALID_TARGET", target)
        obj = matches[0]
        if obj.library or sum(other.get(ID) == obj.get(ID) for other in scene.objects) != 1:
            raise ForgeError("AMBIGUOUS_TARGET", target)
        return obj

    def check_alias(self, scene, alias):
        if any(obj.get(ALIAS) == alias for obj in scene.objects):
            raise ForgeError("ALIAS_EXISTS", alias)

    def enroll(self, scene, obj, name, journal):
        obj[ID] = uuid.uuid4().hex
        obj[ALIAS] = name
        obj.name = name
        collection = scene.collection
        journal.change(
            lambda: collection.objects.unlink(obj) if obj.name in collection.objects else None,
            lambda: collection.objects.link(obj) if obj.name not in collection.objects else None,
        )
        return obj

    def primitive(self, scene, op, name, dimensions, journal):
        self.check_alias(scene, name)
        operator = "uv_sphere" if op == "sphere" else op
        require_finished(getattr(bpy.ops.mesh, f"primitive_{operator}_add")(location=(0, 0, 0)))
        obj = bpy.context.object
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        self.enroll(scene, obj, name, journal)
        bpy.context.view_layer.update()
        if dimensions:
            self.resize(obj, dimensions, journal)
        return obj

    def resize(self, obj, dimensions, journal):
        if obj.type != "MESH":
            raise ForgeError("INVALID_OBJECT_TYPE", obj.name)
        bpy.context.view_layer.update()
        if any(obj.rotation_euler):
            raise ForgeError("ROTATED_DIMENSIONS", "set dimensions before rotating or use @scale")
        scale = tuple(
            old_scale * requested / actual if actual else old_scale
            for old_scale, requested, actual in zip(obj.scale, dimensions, obj.dimensions)
        )
        journal.assign(obj, "scale", scale)

    def material(self, obj, values, journal):
        if obj.type != "MESH":
            raise ForgeError("INVALID_OBJECT_TYPE", obj.name)
        mesh = obj.data.copy()
        previous = mesh.materials[0] if mesh.materials else None
        mat = previous.copy() if previous else bpy.data.materials.new(f"Forge {obj.get(ALIAS)}")
        mat.use_nodes = True
        node = next((node for node in mat.node_tree.nodes if node.type == "BSDF_PRINCIPLED"), None)
        if node is None:
            raise ForgeError("UNSUPPORTED_MATERIAL", "expected a Principled BSDF")
        if "color" in values:
            rgba = (*rgb(values["color"]), node.inputs["Alpha"].default_value)
            node.inputs["Base Color"].default_value = rgba
            mat.diffuse_color = rgba
        for key in ("roughness", "metallic", "alpha"):
            if key in values:
                node.inputs[key.capitalize()].default_value = values[key]
                if key == "alpha":
                    mat.diffuse_color[3] = values[key]
        if mesh.materials:
            mesh.materials[0] = mat
        else:
            mesh.materials.append(mat)
        journal.assign(obj, "data", mesh)

    def hole(self, obj, values, journal):
        if obj.type != "MESH" or obj.modifiers or not all(obj.dimensions):
            raise ForgeError("INVALID_OBJECT_TYPE", "hole requires a solid mesh without modifiers")
        bpy.context.view_layer.update()
        center = obj.matrix_world @ (
            sum((Vector(corner) for corner in obj.bound_box), Vector()) / 8
        )
        center += Vector(values.get("at", (0, 0, 0)))
        require_finished(
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=48,
                radius=values["d"] / 2,
                depth=max(obj.dimensions) * 4,
                location=center,
            )
        )
        cutter = bpy.context.object
        cutter_mesh = cutter.data
        modifier = None
        try:
            modifier = obj.modifiers.new("Forge Hole", "BOOLEAN")
            modifier.object = cutter
            modifier.operation = "DIFFERENCE"
            modifier.solver = "EXACT"
            depsgraph = bpy.context.evaluated_depsgraph_get()
            mesh = bpy.data.meshes.new_from_object(
                obj.evaluated_get(depsgraph), depsgraph=depsgraph
            )
            if not mesh.polygons:
                bpy.data.meshes.remove(mesh)
                raise ForgeError("EMPTY_GEOMETRY", "hole would remove the entire mesh")
            journal.assign(obj, "data", mesh)
        finally:
            if modifier:
                obj.modifiers.remove(modifier)
            bpy.data.objects.remove(cutter, do_unlink=True)
            bpy.data.meshes.remove(cutter_mesh)

    def animate(self, obj, op, values, journal):
        anim = obj.animation_data_create()
        original_action, original_slot = anim.action, anim.action_slot
        action = (
            original_action.copy()
            if original_action
            else bpy.data.actions.new(f"Forge {obj.get(ALIAS)}")
        )
        path = {"~move": "location", "~scale": "scale", "~rotate": "rotation_euler"}[op]
        original_value = getattr(obj, path).copy()
        start, end = values["frames"]

        def restore():
            anim.action = original_action
            if original_slot:
                anim.action_slot = original_slot
            setattr(obj, path, original_value)

        def activate():
            anim.action = action
            if original_slot:
                anim.action_slot = action.slots.get(original_slot.identifier)
            setattr(obj, path, original_value)

        journal.change(restore, activate)
        index = -1
        if op == "~rotate":
            if obj.rotation_mode in {"QUATERNION", "AXIS_ANGLE"}:
                raise ForgeError("ROTATION_MODE", "Euler rotation mode required")
            index = "xyz".index(values["axis"])
            first, last = original_value.copy(), original_value.copy()
            last[index] += math.radians(values["deg"])
        else:
            first, last = values["from"], values["to"]
        for frame, value in ((start, first), (end, last)):
            setattr(obj, path, value)
            if not obj.keyframe_insert(data_path=path, index=index, frame=frame):
                raise ForgeError("KEYFRAME_FAILED", obj.name)
        setattr(obj, path, original_value)
        assigned_slot = anim.action_slot

        def redo():
            anim.action = action
            anim.action_slot = assigned_slot
            setattr(obj, path, original_value)

        journal.steps[-1] = (restore, redo)

    def dispatch(self, scene, cmd, journal, export):
        op, target, values = cmd.op, cmd.target, cmd.values
        if op in PRIMITIVE_OPS:
            return self.primitive(scene, op[1:], target, values.get("size"), journal)
        if op == "!timeline":
            start, end = values["frames"]
            # Blender clamps either property against the other.
            ordered = [("frame_end", end), ("frame_start", start)]
            if end < scene.frame_start:
                ordered.reverse()
            for prop, value in ordered:
                journal.assign(scene, prop, value)
            return None
        if op == "!export":
            return export(target, values["path"], False)
        if op in {"+camera", "+light"}:
            self.check_alias(scene, target)
            if op == "+camera":
                data = bpy.data.cameras.new(target)
            else:
                data = bpy.data.lights.new(target, values.get("type", "point").upper())
                if "power" in values:
                    data.energy = values["power"]
                if "color" in values:
                    data.color = rgb(values["color"])
            return self.enroll(scene, bpy.data.objects.new(target, data), target, journal)

        obj = self.find(scene, target)
        if op == "?":
            bpy.context.view_layer.update()
            return object_info(obj)
        if op == "-":
            collections = tuple(obj.users_collection)
            if collections != (scene.collection,) or obj.children or scene.camera == obj:
                raise ForgeError(
                    "DELETE_RESTRICTED", "detach children and retain a single root collection"
                )
            collection = collections[0]
            journal.change(
                lambda: collection.objects.link(obj), lambda: collection.objects.unlink(obj)
            )
        elif op == "+copy":
            self.check_alias(scene, values["as"])
            copy = obj.copy()
            if obj.data:
                copy.data = obj.data.copy()
            return self.enroll(scene, copy, values["as"], journal)
        elif op == "+hole":
            self.hole(obj, values, journal)
        elif op == "@size":
            self.resize(obj, values["value"], journal)
        elif op == "@rot":
            if obj.rotation_mode in {"QUATERNION", "AXIS_ANGLE"}:
                raise ForgeError("ROTATION_MODE", "Euler rotation mode required")
            journal.assign(obj, "rotation_euler", tuple(map(math.radians, values["value"])))
        elif op in {"@pos", "@scale"}:
            journal.assign(obj, {"@pos": "location", "@scale": "scale"}[op], values["value"])
        elif op in {"@color", "@material"}:
            self.material(obj, {"color": values["value"]} if op == "@color" else values, journal)
        elif op == "@energy":
            if obj.type != "LIGHT":
                raise ForgeError("INVALID_OBJECT_TYPE", obj.name)
            light = obj.data.copy()
            light.energy = values["value"]
            journal.assign(obj, "data", light)
        elif op == "@parent":
            parent = self.find(scene, values["value"])
            ancestor = parent
            while ancestor:
                if ancestor == obj:
                    raise ForgeError("PARENT_CYCLE", target)
                ancestor = ancestor.parent
            journal.assign(obj, "parent", parent)
        elif op == "!camera":
            if obj.type != "CAMERA":
                raise ForgeError("INVALID_OBJECT_TYPE", obj.name)
            journal.assign(scene, "camera", obj)
        elif op.startswith("~"):
            self.animate(obj, op, values, journal)
        else:
            raise ForgeError("UNKNOWN_OPERATION", op)
        return obj

    def execute(self, scene, script, export):
        commands = parse(script)
        journal = Journal()
        selected = tuple(bpy.context.selected_objects)
        active = bpy.context.view_layer.objects.active
        ids, results = [], []
        try:
            for cmd in commands:
                result = self.dispatch(scene, cmd, journal, export)
                if isinstance(result, bpy.types.Object):
                    ids.append(result[ID])
                elif result is not None:
                    results.append(result)
            bpy.context.view_layer.update()
        except Exception as exc:
            journal.rollback()
            bpy.context.view_layer.update()
            bpy.ops.object.select_all(action="DESELECT")
            for obj in selected:
                if obj.name in bpy.context.view_layer.objects:
                    obj.select_set(True)
            if active and active.name in bpy.context.view_layer.objects:
                bpy.context.view_layer.objects.active = active
            if isinstance(exc, ForgeError):
                raise ForgeError(exc.code, exc.detail, cmd.line) from exc
            LOG.exception("Blender operation failed")
            raise ForgeError("BLENDER_ERROR", str(exc).splitlines()[0][:240], cmd.line) from exc
        if journal.steps:
            self.past.append((scene, journal))
            self.past = self.past[-20:]
            self.future.clear()
            last = next((obj for obj in scene.objects if ids and obj.get(ID) == ids[-1]), None)
            if last and last.name in bpy.context.view_layer.objects and last.visible_get():
                bpy.ops.object.select_all(action="DESELECT")
                last.select_set(True)
                bpy.context.view_layer.objects.active = last
        response = {"ok": True, "message": f"OK {len(commands)}", "count": len(commands)}
        if ids:
            response["ids"] = list(dict.fromkeys(ids))
        if results:
            response["results"] = results
        return response

    def history(self, scene, reverse):
        source, destination = (self.past, self.future) if reverse else (self.future, self.past)
        if not source or source[-1][0] != scene:
            raise ForgeError("NO_HISTORY", "no eligible batch for the active scene")
        entry = source[-1]
        try:
            entry[1].replay(reverse)
        except Exception as exc:
            self.clear_history()
            LOG.exception("History invalidated")
            raise ForgeError("HISTORY_INVALID", "scene data changed outside Forge") from exc
        destination.append(source.pop())
        bpy.context.view_layer.update()
        return {"ok": True, "message": "OK 1"}


PRIMITIVE_OPS = {f"+{name}" for name in PRIMITIVES}

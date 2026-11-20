"""Local command queue and request dispatcher for one approved Blender scene."""

import logging
import re
import tempfile
import time
import uuid
from pathlib import Path

import bpy

from .engine import ID, Engine, object_info, require_finished
from .exchange import MAX_REQUEST, PROTOCOL, REQUEST_ID, read_json, write_json
from .exporting import export, publish, safe_name
from .language import VERSION, ForgeError

LOG = logging.getLogger(__name__)
DETAILS = {"basic", "hierarchy", "geometry", "materials", "animation", "all"}


class Service:
    def __init__(self):
        self.engine = Engine()
        self.directory = None
        self.scene = None
        self.root = None
        self.last = "Idle"
        self.last_request = 0.0
        self.agent = ""
        self.log_handler = None
        self.render_job = None

    def start(self, scene, root="", parent=None):
        if self.directory:
            raise ForgeError("ALREADY_RUNNING", "stop the current connection first")
        if root:
            resolved = Path(root).expanduser().resolve()
            if not resolved.is_dir():
                raise ForgeError("INVALID_PATH", "select an existing export folder")
            self.root = resolved
        else:
            self.root = None
        directory = Path(tempfile.mkdtemp(prefix="kitquen-forge-", dir=parent))
        try:
            descriptor = directory / "session.json"
            write_json(descriptor, {"protocol": PROTOCOL, "created": time.time()})
            log = logging.FileHandler(directory / "forge.log", encoding="utf-8")
        except Exception:
            for path in directory.iterdir():
                path.unlink()
            directory.rmdir()
            raise
        log.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        package_logger = logging.getLogger(__package__)
        package_logger.addHandler(log)
        package_logger.setLevel(logging.INFO)
        self.log_handler = log
        self.directory, self.scene = directory, scene
        self.last = "Listening"
        self.last_request = 0.0
        self.agent = ""
        return descriptor

    def stop(self):
        if self.directory:
            (self.directory / "session.json").unlink(missing_ok=True)
            for path in self.directory.iterdir():
                if path.name != "forge.log" and path.suffix in {".request", ".response", ".tmp"}:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        LOG.warning("Could not remove %s", path.name)
        if self.log_handler:
            logging.getLogger(__package__).removeHandler(self.log_handler)
            self.log_handler.close()
            self.log_handler = None
        self.directory, self.scene, self.root = None, None, None
        self.engine.clear_history()
        self.render_job = None
        self.last = "Stopped"

    def scene_info(self, scene):
        return {
            "ok": True,
            "scene": scene.name,
            "objects": len(scene.objects),
            "managed": sum(ID in obj for obj in scene.objects),
            "frame_range": [scene.frame_start, scene.frame_end],
        }

    def export(self, fmt, name, selected):
        return export(self.root, fmt, name, selected)

    def dispatch(self, action, args):
        scene = self.scene
        if scene is None:
            raise ForgeError("OFFLINE", "start the connection from the Blender panel")
        if action == "status":
            return {
                "ok": True,
                "version": "0.1.0",
                "language": VERSION,
                "protocol": PROTOCOL,
                "scene": scene.name,
                "active": bpy.context.scene == scene,
                "last": self.last,
                "exports_enabled": self.root is not None,
            }
        if args.get("scene") != scene.name or bpy.context.scene != scene:
            raise ForgeError("WRONG_SCENE", f"activate and specify {scene.name}")
        if action == "summary":
            return self.scene_info(scene)
        if action == "inspect":
            detail = args.get("detail", "basic")
            target = args.get("target", "managed")
            if not isinstance(detail, str) or detail not in DETAILS or not isinstance(target, str):
                raise ForgeError("INVALID_REQUEST", "invalid inspection filter")
            offset, limit = args.get("offset", 0), args.get("limit", 10)
            if (
                type(offset) is not int
                or type(limit) is not int
                or offset < 0
                or not 1 <= limit <= 32
            ):
                raise ForgeError("INVALID_REQUEST", "offset >= 0 and 1 <= limit <= 32 required")
            if target == "managed":
                objects = [obj for obj in scene.objects if ID in obj]
            elif target == "selected":
                objects = bpy.context.selected_objects
            else:
                objects = [self.engine.find(scene, target.removeprefix("id:"))]
            bpy.context.view_layer.update()
            return {
                "ok": True,
                "total": len(objects),
                "objects": [object_info(obj, detail) for obj in objects[offset : offset + limit]],
            }
        if bpy.context.mode != "OBJECT":
            raise ForgeError("OBJECT_MODE_REQUIRED", "switch Blender to Object Mode")
        if action == "execute":
            return self.engine.execute(scene, args.get("script"), self.export)
        if action in {"undo", "redo"}:
            return self.engine.history(scene, action == "undo")
        if action == "export":
            selected = args.get("selected", False)
            if type(selected) is not bool:
                raise ForgeError("INVALID_REQUEST", "selected must be true or false")
            return self.export(args.get("format"), args.get("name"), selected)
        if action == "render_status":
            if not self.render_job or args.get("job") != self.render_job["job"]:
                raise ForgeError("INVALID_JOB", "unknown render job")
            return dict(self.render_job)
        if action == "render_start":
            return self.schedule_render(scene, args)
        raise ForgeError("INVALID_REQUEST", "unknown bridge action")

    def schedule_render(self, scene, args):
        name = safe_name("png", args.get("name"))
        if self.root is None or not self.root.is_dir():
            raise ForgeError("EXPORT_ROOT_REQUIRED", "choose an existing export folder in Blender")
        if self.render_job and self.render_job["status"] in {"queued", "running"}:
            raise ForgeError("RENDER_BUSY", "a render job is already pending")
        if scene.camera is None:
            raise ForgeError("NO_CAMERA", "set the active camera before rendering")
        engine = args.get("engine", "workbench")
        width, height = args.get("width", 640), args.get("height", 480)
        if engine not in {"workbench", "eevee", "cycles"} or any(
            type(n) is not int or not 16 <= n <= 2048 for n in (width, height)
        ):
            raise ForgeError("INVALID_REQUEST", "engine or resolution is out of range")
        self.render_job = {"ok": True, "job": uuid.uuid4().hex, "status": "queued"}
        job = self.render_job
        root = self.root
        session = self.directory

        def render():
            if self.directory != session or bpy.context.scene != scene:
                job.update(ok=False, status="failed", code="WRONG_SCENE")
                return None
            job["status"] = "running"
            settings = scene.render
            image = settings.image_settings
            old = (
                settings.engine,
                settings.resolution_x,
                settings.resolution_y,
                settings.resolution_percentage,
                settings.filepath,
                image.file_format,
                settings.use_compositing,
                settings.use_sequencer,
            )
            try:
                with tempfile.TemporaryDirectory(prefix=".forge-", dir=root) as folder:
                    staging = Path(folder)
                    settings.engine = {
                        "workbench": "BLENDER_WORKBENCH",
                        "eevee": "BLENDER_EEVEE",
                        "cycles": "CYCLES",
                    }[engine]
                    settings.resolution_x, settings.resolution_y = width, height
                    settings.resolution_percentage = 100
                    settings.filepath = str(staging / name)
                    image.file_format = "PNG"
                    settings.use_compositing = False
                    settings.use_sequencer = False
                    require_finished(bpy.ops.render.render(write_still=True))
                    if not (staging / name).is_file():
                        raise ForgeError("RENDER_FAILED", name)
                    job.update(status="complete", files=publish(staging, root))
            except Exception:
                LOG.exception("Render failed")
                job.update(ok=False, status="failed", code="RENDER_FAILED")
            finally:
                (
                    settings.engine,
                    settings.resolution_x,
                    settings.resolution_y,
                    settings.resolution_percentage,
                    settings.filepath,
                    image.file_format,
                    settings.use_compositing,
                    settings.use_sequencer,
                ) = old
            self.last = f"Render {job['status']}"
            self.last_request = time.time()
            return None

        bpy.app.timers.register(render, first_interval=0.3)
        return dict(job)

    def tick(self):
        if self.directory is None:
            return None
        try:
            path = next(
                (p for p in self.directory.glob("*.request") if REQUEST_ID.fullmatch(p.stem)), None
            )
            if path is not None:
                self.consume(path)
        except OSError:
            LOG.exception("Local request queue failed")
        return 0.1

    def consume(self, path):
        request = {}
        action = None
        try:
            request = read_json(path, MAX_REQUEST)
            if (
                request.get("protocol") != PROTOCOL
                or type(request.get("deadline")) not in (int, float)
                or not time.time() <= request["deadline"] <= time.time() + 180
                or not isinstance(request.get("args"), dict)
                or not isinstance(request.get("action"), str)
            ):
                raise ForgeError("INVALID_REQUEST", "invalid protocol, body, or request deadline")
            action = request["action"]
            agent = request.get("agent")
            self.agent = re.sub(r"[^\w .-]", "", agent)[:48] if isinstance(agent, str) else "MCP"
            self.last_request = time.time()
            response = self.dispatch(action, request["args"])
        except ForgeError as exc:
            response = exc.response()
        except (ValueError, OSError):
            LOG.exception("Malformed bridge request")
            response = ForgeError("INVALID_REQUEST", "invalid local request").response()
        except Exception:
            LOG.exception("Bridge operation failed")
            response = ForgeError("BLENDER_ERROR", "see Blender session log").response()
        if action not in {"status", "render_status"}:
            self.last = response.get("message", action or "Invalid request")
            LOG.info("%s %s", action, self.last)
        try:
            write_json(path.with_suffix(".response"), response)
        finally:
            path.unlink(missing_ok=True)

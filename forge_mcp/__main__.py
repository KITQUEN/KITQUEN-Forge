"""Launch a Forge MCP server against an explicitly selected Blender session."""

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import CallToolResult, TextContent

from kitquen_forge.exchange import MAX_REQUEST, PROTOCOL, read_json, write_json
from kitquen_forge.language import VERSION, ForgeError, parse, serialize

Format = Literal["stl", "obj", "glb", "blend"]
Detail = Literal["basic", "hierarchy", "geometry", "materials", "animation", "all"]
HELP = {
    "syntax": "+cube/base size=4,4,2\n@pos/base 0,0,1\n@color/base #FF6600\n?/base",
    "modeling": "+cube|sphere|cylinder|cone|plane|torus/alias [size=1|x,y,z]; "
    "+hole/id d=1 [at=x,y,z]; +copy/id as=alias; "
    "@pos|rot|scale|size/id x,y,z; @parent/id parent; -/id",
    "animation": "~move/id from=0,0,0 to=1,0,0 frames=1:24; "
    "~scale/id from=1 to=2 frames=1:24; ~rotate/id axis=z deg=90 frames=1:24; "
    "!timeline 1:24",
    "materials": "@color/id #FF6600; @material/id color=#FF6600 roughness=0.4 metallic=0 alpha=1",
    "rendering": "+camera/cam; @pos/cam 0,0,10; !camera/cam; +light/key type=point power=500. "
    "Use forge_render with name to queue, then job to poll.",
    "export": "forge_export uses the approved Blender folder. Use a simple filename. "
    "Inline !export/stl model.stl must be last. GLB carries supported materials/animation.",
    "errors": "ERR <line> <code> <detail>. Use forge_status, active scene, and forge_inspect. "
    "A timeout can leave an operation in progress. Inspect before retrying.",
}


def request(session: Path, action: str, agent: str, **args) -> dict:
    token = uuid.uuid4().hex
    outgoing = session.parent / f"{token}.request"
    incoming = outgoing.with_suffix(".response")
    try:
        try:
            if read_json(session, 1024).get("protocol") != PROTOCOL:
                raise ValueError("protocol mismatch")
        except (OSError, ValueError):
            return ForgeError("OFFLINE", "copy a live Blender session path").response()
        duration = 90 if action in {"export", "execute"} else 12
        deadline = time.time() + duration
        write_json(
            outgoing,
            {
                "protocol": PROTOCOL,
                "deadline": deadline,
                "agent": agent,
                "action": action,
                "args": args,
            },
        )
        until = time.monotonic() + duration
        while time.monotonic() < until:
            if incoming.is_file():
                return read_json(incoming, 8 * MAX_REQUEST)
            if not session.is_file():
                return ForgeError("OFFLINE", "Blender stopped the connection").response()
            time.sleep(0.08)
        return ForgeError("TIMEOUT", "inspect Blender before retrying").response()
    except (OSError, ValueError):
        return ForgeError("IO_ERROR", "local queue is unavailable").response()
    finally:
        for path in (outgoing, incoming):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def reply(data: dict) -> CallToolResult:
    if data.get("ok") is False and "message" in data:
        message = data["message"]
    elif "count" in data and "message" in data and "results" not in data:
        message = " ".join((data["message"], *data.get("ids", [])))
    else:
        message = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return CallToolResult(content=[TextContent(type="text", text=message)], structuredContent=data)


def create_server(session: Path) -> FastMCP:
    mcp = FastMCP("KITQUEN Forge", instructions="Use forge_status to get the approved scene.")

    def send(context, action, **args):
        parameters = context.session.client_params
        agent = parameters.clientInfo.name if parameters else "MCP"
        return reply(request(session, action, agent, **args))

    @mcp.tool()
    def forge_status(ctx: Context) -> CallToolResult:
        """Check the local Blender connection and get the approved scene name."""
        return send(ctx, "status")

    @mcp.tool()
    def forge_execute(scene: str, script: str, ctx: Context) -> CallToolResult:
        """Apply one Kitlean 3D batch to the active approved scene."""
        try:
            parse(script)
        except ForgeError as exc:
            return reply(exc.response())
        return send(ctx, "execute", scene=scene, script=script)

    @mcp.tool()
    def forge_inspect(
        scene: str,
        ctx: Context,
        target: str = "managed",
        detail: Detail = "basic",
        offset: int = 0,
        limit: int = 10,
    ) -> CallToolResult:
        """Inspect managed objects, selected objects, or one Forge alias/ID (prefix id: optional)."""
        return send(
            ctx, "inspect", scene=scene, target=target, detail=detail, offset=offset, limit=limit
        )

    @mcp.tool()
    def forge_help(
        topic: Literal[
            "syntax", "modeling", "animation", "materials", "rendering", "export", "errors"
        ] = "syntax",
    ) -> str:
        """Retrieve one short Kitlean reference topic."""
        return HELP[topic]

    @mcp.tool()
    def forge_validate(
        script: str, convert_to: Literal["compact", "readable"] | None = None
    ) -> CallToolResult:
        """Parse and validate syntax offline. Optionally convert between dialects."""
        try:
            commands = parse(script)
        except ForgeError as exc:
            return reply(exc.response())
        result = {"ok": True, "count": len(commands), "language": VERSION}
        if convert_to:
            result["script"] = serialize(commands, readable=convert_to == "readable")
        return reply(result)

    @mcp.tool()
    def forge_scene_summary(scene: str, ctx: Context) -> CallToolResult:
        """Return object counts and frame range for the approved scene."""
        return send(ctx, "summary", scene=scene)

    @mcp.tool()
    def forge_undo(scene: str, ctx: Context) -> CallToolResult:
        """Undo the latest reversible Forge batch in this session."""
        return send(ctx, "undo", scene=scene)

    @mcp.tool()
    def forge_redo(scene: str, ctx: Context) -> CallToolResult:
        """Redo the latest undone Forge batch."""
        return send(ctx, "redo", scene=scene)

    @mcp.tool()
    def forge_export(
        scene: str, format: Format, name: str, ctx: Context, selected: bool = False
    ) -> CallToolResult:
        """Write STL, OBJ, GLB or a BLEND copy to the Blender-approved folder."""
        return send(ctx, "export", scene=scene, format=format, name=name, selected=selected)

    @mcp.tool()
    def forge_render(
        scene: str,
        ctx: Context,
        name: str = "",
        job: str = "",
        width: int = 640,
        height: int = 480,
        engine: Literal["workbench", "eevee", "cycles"] = "workbench",
    ) -> CallToolResult:
        """Queue a PNG still by name or check a render job by ID."""
        if bool(name) == bool(job):
            return reply(
                ForgeError("INVALID_REQUEST", "provide exactly one of name or job").response()
            )
        if job:
            return send(ctx, "render_status", scene=scene, job=job)
        return send(
            ctx, "render_start", scene=scene, name=name, width=width, height=height, engine=engine
        )

    return mcp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path, help="Blender session.json path")
    args = parser.parse_args()
    create_server(args.session.expanduser().resolve()).run(transport="stdio")


if __name__ == "__main__":
    main()

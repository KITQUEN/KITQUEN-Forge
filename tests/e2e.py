"""Use the official MCP client to edit a real Blender scene through stdio."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def check(descriptor, root, live):
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "forge_mcp", "--session", descriptor], cwd=ROOT
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {item.name for item in (await session.list_tools()).tools}
        assert len(tools) == 10, tools

        async def call(tool, **args):
            result = await session.call_tool(f"forge_{tool}", args)
            assert not result.isError, result
            return result.structuredContent

        status = await call("status")
        assert status["active"], status
        scene = status["scene"]
        bad = await call("execute", scene="wrong", script="+cube/base")
        assert bad["code"] == "WRONG_SCENE", bad
        good = await call(
            "execute",
            scene=scene,
            script="+cube/base size=2\n"
            "@pos/base 2,0,0\n@color/base #FF6600\n"
            "~move/base from=2,0,0 to=3,0,0 frames=1:24",
        )
        assert good["ok"], good
        stable = good["ids"][0]
        found = await call("inspect", scene=scene, target=stable, detail="all")
        assert found["objects"][0]["id"] == stable, found
        assert found["objects"][0]["mesh"]["vertices"] == 8, found
        assert (await call("undo", scene=scene))["ok"]
        assert (await call("scene_summary", scene=scene))["managed"] == 0
        assert (await call("redo", scene=scene))["ok"]
        assert (await call("inspect", scene=scene, target=stable))["ok"]
        exported = await call("export", scene=scene, format="glb", name="agent.glb", selected=False)
        assert exported["ok"], exported
        assert (root / "agent.glb").read_bytes()[:4] == b"glTF"
        if live:
            queued = await call(
                "render", scene=scene, name="preview.png", engine="workbench", width=64, height=64
            )
            assert queued.get("status") == "queued", queued
            for _ in range(30):
                await asyncio.sleep(0.5)
                state = await call("render", scene=scene, job=queued["job"])
                if state.get("status") not in {"queued", "running"}:
                    break
            assert state.get("status") == "complete", state
            assert (root / "preview.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


async def run(blender, parent, live):
    with tempfile.TemporaryDirectory(prefix="forge-e2e-", dir=parent) as directory:
        root = Path(directory)
        with (root / "blender.log").open("w+", encoding="utf-8") as log:
            startup = None
            if sys.platform == "win32" and live:
                startup = subprocess.STARTUPINFO()
                startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            environment = {
                **os.environ,
                "TEMP": str(root),
                "TMP": str(root),
                "BLENDER_USER_RESOURCES": str(root / "user"),
            }
            process = subprocess.Popen(
                [
                    str(blender),
                    *([] if live else ["-b"]),
                    "--factory-startup",
                    "--python-exit-code",
                    "1",
                    "--python",
                    str(ROOT / "tests" / "blender_bridge_host.py"),
                    "--",
                    str(root),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                env=environment,
                startupinfo=startup,
            )
            try:
                ready = root / "ready.json"
                async with asyncio.timeout(45):
                    while not ready.is_file():
                        if process.poll() is not None:
                            raise RuntimeError(f"Blender exited with {process.returncode}")
                        await asyncio.sleep(0.1)
                    descriptor = json.loads(ready.read_text(encoding="utf-8"))["session"]
                    await check(descriptor, root, live)
            except Exception:
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                (root / "stop").touch()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    print("FORGE MCP TO BLENDER PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--temp", type=Path, default=ROOT / "build")
    parser.add_argument(
        "--live", action="store_true", help="Exercise the interactive timer and render"
    )
    options = parser.parse_args()
    options.temp.mkdir(exist_ok=True, parents=True)
    asyncio.run(run(options.blender, options.temp.resolve(), options.live))

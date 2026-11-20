import asyncio
import sys
import unittest
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpTests(unittest.TestCase):
    def test_stdio_schemas_and_offline_validation(self):
        asyncio.run(self.check_stdio())

    async def check_stdio(self):
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "forge_mcp", "--session", "missing/session.json"],
            cwd=Path(__file__).resolve().parents[1],
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as session,
        ):
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            self.assertEqual(len(tools), 10)
            self.assertEqual(
                set(tools["forge_execute"].inputSchema["required"]), {"scene", "script"}
            )
            result = await session.call_tool("forge_validate", {"script": "+cube/base size=2"})
            self.assertTrue(result.structuredContent["ok"])
            result = await session.call_tool("forge_status", {})
            self.assertEqual(result.structuredContent["code"], "OFFLINE")

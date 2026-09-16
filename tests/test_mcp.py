"""Exercise the public CLI through an actual MCP client and stdio transport."""

import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_repository_query_over_stdio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            await asyncio.to_thread(
                subprocess.run, ["git", "init", "-q", str(root)], check=True
            )
            source = root / "auth.py"
            source.write_text(
                "class Auth:\n    def login(self): pass\n", encoding="utf-8"
            )
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "agent_context.cli", "serve", str(root)],
            )
            async with asyncio.timeout(30):
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as session:
                        initialized = await session.initialize()
                        self.assertEqual(initialized.serverInfo.name, "agent-context")
                        tools = (await session.list_tools()).tools
                        self.assertEqual([tool.name for tool in tools], ["query_code"])
                        tool = tools[0]
                        self.assertTrue(tool.annotations.readOnlyHint)
                        self.assertEqual(
                            set(tool.inputSchema["properties"]), {"text", "limit"}
                        )
                        self.assertEqual(
                            tool.inputSchema["properties"]["limit"]["maximum"], 100
                        )
                        missing = await session.call_tool("query_code", {"text": ""})
                        self.assertTrue(missing.isError)
                        self.assertIn("index first", missing.content[0].text)
                        self.assertFalse((root / ".agent-context").exists())

                        def cli(*args):
                            result = subprocess.run(
                                [sys.executable, "-m", "agent_context.cli", *args],
                                capture_output=True,
                                text=True,
                                check=True,
                            )
                            return json.loads(result.stdout)

                        await asyncio.to_thread(cli, "index", directory)
                        expected = await asyncio.to_thread(
                            cli, "query", directory, "LOGIN"
                        )
                        found = await session.call_tool("query_code", {"text": "LOGIN"})
                        self.assertFalse(found.isError)
                        self.assertEqual(found.structuredContent, expected)
                        self.assertEqual(json.loads(found.content[0].text), expected)
                        self.assertEqual(
                            found.structuredContent["results"][0]["qualified_name"],
                            "Auth.login",
                        )
                        limited = await session.call_tool(
                            "query_code", {"text": "", "limit": 1}
                        )
                        self.assertTrue(limited.structuredContent["truncated"])
                        self.assertEqual(len(limited.structuredContent["results"]), 1)
                        for limit in [0, 101, 1.5, True, "2"]:
                            invalid = await session.call_tool(
                                "query_code", {"text": "", "limit": limit}
                            )
                            self.assertTrue(invalid.isError, limit)
                        unknown = await session.call_tool("not_a_tool", {})
                        self.assertTrue(unknown.isError)
                        empty = await session.call_tool(
                            "query_code", {"text": "no_such_symbol"}
                        )
                        self.assertEqual(empty.structuredContent["results"], [])
                        # The same running server sees a newly persisted snapshot.
                        source.write_text("def refreshed(): pass\n", encoding="utf-8")
                        await asyncio.to_thread(cli, "index", directory)
                        refreshed = await session.call_tool(
                            "query_code", {"text": "refreshed"}
                        )
                        self.assertEqual(
                            refreshed.structuredContent,
                            await asyncio.to_thread(
                                cli, "query", directory, "refreshed"
                            ),
                        )

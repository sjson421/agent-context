import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_context.graph import extract


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, "-m", "agent_context.cli", *map(str, args)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return json.loads(result.stdout if success else result.stderr)

    def test_index_query_and_replace_snapshot(self):
        source = self.root / "auth.py"
        source.write_text(
            "class Auth:\n"
            "    async def login(self):\n"
            "        def check():\n"
            "            return True\n"
            "        return check()\n",
            encoding="utf-8",
        )
        indexed = self.cli("index", self.root)
        self.assertEqual(
            (indexed["files"], indexed["nodes"], indexed["edges"]), (1, 4, 3)
        )
        found = self.cli("query", self.root, "LOGIN")
        self.assertEqual(
            [(node["qualified_name"], node["kind"]) for node in found["results"]],
            [("Auth.login", "method"), ("Auth.login.check", "function")],
        )
        method, nested = found["results"]
        self.assertEqual(nested["parent_id"], method["id"])
        self.assertEqual(
            (method["path"], method["line"], method["end_line"]), ("auth.py", 2, 5)
        )
        self.assertTrue(self.cli("query", self.root, "", "--limit", 1)["truncated"])
        self.assertEqual(self.cli("index", self.root), indexed)
        self.assertEqual(self.cli("query", self.root, "LOGIN"), found)
        source.unlink()
        self.cli("index", self.root)
        self.assertEqual(self.cli("query", self.root, "")["results"], [])

    def test_git_selection_and_symlink_boundary(self):
        (self.root / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
        (self.root / "ignored.py").write_text("invalid python!", encoding="utf-8")
        (self.root / "tracked.py").write_text("def tracked(): pass\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "tracked.py"], check=True)
        (self.root / "untracked.py").write_bytes(
            b"# coding: latin-1\n# caf\xe9\ndef fresh(): pass\n"
        )
        (self.root / "link.py").symlink_to(self.root / "tracked.py")
        (self.root / "text.txt").write_text("not Python", encoding="utf-8")
        self.assertEqual(self.cli("index", self.root)["files"], 2)
        self.assertEqual(len(self.cli("query", self.root, "fresh")["results"]), 1)

    def test_parse_failure_preserves_last_snapshot(self):
        source = self.root / "sample.py"
        source.write_text("def original(): pass\n", encoding="utf-8")
        self.cli("index", self.root)
        before = self.cli("query", self.root, "")
        source.write_text("def broken(\n", encoding="utf-8")
        self.assertIn("sample.py", self.cli("index", self.root, success=False)["error"])
        self.assertEqual(self.cli("query", self.root, ""), before)

    def test_missing_index_invalid_repository_and_limit(self):
        self.assertIn(
            "index first", self.cli("query", self.root, "x", success=False)["error"]
        )
        self.assertFalse((self.root / ".agent-context").exists())
        self.assertIn(
            "Git", self.cli("index", self.root / "missing", success=False)["error"]
        )
        self.assertIn(
            "limit",
            self.cli("query", self.root, "x", "--limit", 0, success=False)["error"],
        )

    def test_query_treats_sql_and_wildcards_as_literal(self):
        (self.root / "test.py").write_text("def example(): pass\n", encoding="utf-8")
        self.cli("index", self.root)
        for term in ["%", "_", "' OR 1=1 --"]:
            self.assertEqual(self.cli("query", self.root, term)["results"], [])

    def test_write_failure_rolls_back_snapshot(self):
        source = self.root / "sample.py"
        source.write_text("def original(): pass\n", encoding="utf-8")
        self.cli("index", self.root)
        before = self.cli("query", self.root, "")
        connection = sqlite3.connect(self.root / ".agent-context" / "graph.sqlite3")
        self.addCleanup(connection.close)
        with connection:
            connection.execute(
                "CREATE TRIGGER fail_insert BEFORE INSERT ON nodes "
                "BEGIN SELECT RAISE(ABORT, 'test write failure'); END"
            )
        source.write_text("def replacement(): pass\n", encoding="utf-8")
        self.assertIn(
            "test write failure", self.cli("index", self.root, success=False)["error"]
        )
        self.assertEqual(self.cli("query", self.root, ""), before)


class ExtractionTests(unittest.TestCase):
    def test_conditional_definitions_and_repeated_names(self):
        nodes, edges = extract(
            "sample.py",
            "if True:\n    def run(): pass\nelse:\n    def run(): pass\n",
        )
        self.assertEqual(len({node["id"] for node in nodes}), 3)
        self.assertEqual(len(edges), 2)
        self.assertTrue(all(edge[0] == nodes[0]["id"] for edge in edges))


if __name__ == "__main__":
    unittest.main()

"""Extract Python definitions and persist a repository snapshot."""

import ast
import json
import sqlite3
import subprocess
import tokenize
from contextlib import closing
from pathlib import Path


def repository_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("repository must be inside a local Git working tree")
    return Path(result.stdout.strip()).resolve()


def extract(path: str, source: str) -> tuple[list[dict], list[tuple]]:
    """Keep lexical ownership explicit; do not infer runtime relationships."""
    tree = ast.parse(source, filename=path)
    nodes = []
    edges = []

    def add(kind, name, qualified_name, line, end_line, parent=None):
        # JSON encoding keeps IDs unambiguous even for unusual filenames.
        node_id = json.dumps([path, kind, qualified_name, line], ensure_ascii=True)
        nodes.append(
            {
                "id": node_id,
                "kind": kind,
                "name": name,
                "qualified_name": qualified_name,
                "path": path,
                "line": line,
                "end_line": end_line,
            }
        )
        if parent is not None:
            edges.append((parent, node_id, "defines"))
        return node_id

    file_id = add("file", path, "", 1, max(1, len(source.splitlines())))

    def walk(node, parent, scope, parent_kind):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = (
                    "class"
                    if isinstance(child, ast.ClassDef)
                    else "method"
                    if parent_kind == "class"
                    else "function"
                )
                qualified = f"{scope}.{child.name}" if scope else child.name
                node_id = add(
                    kind, child.name, qualified, child.lineno, child.end_lineno, parent
                )
                walk(child, node_id, qualified, kind)
            else:
                walk(child, parent, scope, parent_kind)

    walk(tree, file_id, "", "file")
    return nodes, edges


def index_repository(repository: Path) -> dict:
    root = repository_root(repository)
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=True,
    )
    nodes, edges = [], []
    files = 0
    for raw in sorted(set(result.stdout.split(b"\0")) - {b""}):
        path = Path(raw.decode("utf-8", errors="surrogateescape"))
        if path.suffix != ".py":
            continue
        absolute = root / path
        # Never follow repository symlinks, including directory symlinks.
        if any(part.is_symlink() for part in [absolute, *absolute.parents]):
            continue
        if not absolute.is_file():  # A tracked file may be locally deleted.
            continue
        with tokenize.open(absolute) as stream:
            file_nodes, file_edges = extract(path.as_posix(), stream.read())
        files += 1
        nodes.extend(file_nodes)
        edges.extend(file_edges)

    database = root / ".agent-context" / "graph.sqlite3"
    database.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS nodes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, "
            "name TEXT NOT NULL, qualified_name TEXT NOT NULL, path TEXT NOT NULL, "
            "line INTEGER NOT NULL, end_line INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS edges (source TEXT REFERENCES nodes(id), "
            "target TEXT REFERENCES nodes(id), kind TEXT NOT NULL, "
            "PRIMARY KEY (source, target, kind))"
        )
        # Replace atomically: parse or write failures preserve the last snapshot.
        connection.execute("DELETE FROM edges")
        connection.execute("DELETE FROM nodes")
        connection.executemany(
            "INSERT INTO nodes VALUES (:id, :kind, :name, :qualified_name, :path, :line, :end_line)",
            nodes,
        )
        connection.executemany("INSERT INTO edges VALUES (?, ?, ?)", edges)
    return {
        "repository": str(root),
        "files": files,
        "nodes": len(nodes),
        "edges": len(edges),
    }


def query_repository(repository: Path, text: str, limit: int = 20) -> dict:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    root = repository_root(repository)
    database = root / ".agent-context" / "graph.sqlite3"
    if not database.is_file():
        raise ValueError("repository has no index; run agent-context index first")
    with closing(
        sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    ) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT n.*, e.source AS parent_id FROM nodes n "
            "LEFT JOIN edges e ON e.target = n.id AND e.kind = 'defines' "
            "WHERE instr(lower(n.qualified_name), lower(?)) > 0 "
            "OR instr(lower(n.path), lower(?)) > 0 "
            "ORDER BY n.path, n.line, n.kind, n.id LIMIT ?",
            (text, text, limit + 1),
        ).fetchall()
    return {
        "results": [dict(row) for row in rows[:limit]],
        "truncated": len(rows) > limit,
    }

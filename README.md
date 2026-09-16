# agent-context

Local code structure for AI coding agents. Index a Git working tree, persist its
Python definitions in SQLite, and retrieve compact JSON without source dumps.
Everything runs locally; no hosted services or runtime Python dependencies.

This is the first CLI vertical slice, **not yet the full MCP MVP**.

## Install

Requires Python 3.11+ and Git. From a checkout of this project:

```sh
python -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/agent-context --help
```

## Use

```sh
agent-context index /path/to/repository
agent-context query /path/to/repository login
agent-context query /path/to/repository Auth.login --limit 10
```

Use the executable in your virtual environment, or activate it first. A path
inside the working tree also works. To try it on agent-context itself:

```sh
.venv/bin/agent-context index .
.venv/bin/agent-context query . index_repository
```

Index output reports the repository root and file, node, and edge counts.
Query output contains `results` and `truncated`. Each result has an opaque `id`,
`kind`, `name`, `qualified_name`, repository-relative `path`, inclusive `line`
and `end_line`, and `parent_id` identifying its lexical owner (null for files).
Search is an ASCII case-insensitive literal substring of qualified names or paths;
an empty search lists the index. Results have deterministic path/line ordering.
The default limit is 20, with a maximum of 100. Errors return exit code 1 and
a JSON `error` on stderr.

## Index semantics and limits

- Reads the current working-tree versions of tracked and nonignored untracked
  `.py` files, including uncommitted edits. Skips deleted files and symlinks.
  Add `.agent-context/` to the target repository's `.gitignore`.
- Python's standard `ast` parser extracts files, classes, functions, async
  functions, methods, and nested definitions with `defines` relationships.
  Files represent modules for now. Syntax support follows the Python runtime
  running the indexer; source encoding declarations are honored.
- Stores a full snapshot in `.agent-context/graph.sqlite3` inside the repository.
  Reindex after edits; queries read the last successful snapshot. Parse/read
  failures abort indexing and database writes are transactional, preserving
  an existing snapshot. Concurrent successful indexers replace whole snapshots;
  the last writer wins. Source reads are not a filesystem snapshot: avoid
  modifying the working tree during indexing.
- No imports, calls, references, inheritance, semantic search, other languages,
  incremental updates, or MCP transport yet. Definition ownership is lexical,
  not a claim about runtime dispatch. IDs are stable across unchanged indexing,
  but can change when line numbers or names change.
- Full parsing happens in memory before writing. Large-repository performance
  is not yet evaluated. The initial SQLite schema has no migration contract;
  the index is disposable and can be rebuilt from source.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests exercise the CLI in separate processes against temporary Git repositories,
including index replacement, persisted query results, nested ownership, source
encodings, Git ignore rules, symlinks, limits, and failure rollback.

The next vertical slice is MCP access to the existing structured query. Richer
relationships and language support can follow without duplicating graph storage.

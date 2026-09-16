"""JSON command line interface."""

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from agent_context.graph import index_repository, query_repository


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index and query local Python code structure"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help="Replace a repository's local index")
    index.add_argument("repository", type=Path)
    query = commands.add_parser("query", help="Search symbol names and file paths")
    query.add_argument("repository", type=Path)
    query.add_argument("text")
    query.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.command == "index":
            result = index_repository(args.repository)
        else:
            result = query_repository(args.repository, args.text, args.limit)
    except (
        OSError,
        ValueError,
        SyntaxError,
        UnicodeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ) as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

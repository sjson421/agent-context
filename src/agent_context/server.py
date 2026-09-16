"""Repository-bound, read-only MCP access to the persisted graph."""

from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from agent_context.graph import query_repository, repository_root


def create_server(repository: Path) -> FastMCP:
    root = repository_root(repository)
    server = FastMCP(
        "agent-context",
        instructions=(
            f"Query Python code structure indexed from {root}. "
            "Results reflect the last successful agent-context index, not live source."
        ),
    )

    @server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    )
    def query_code(
        text: str,
        limit: Annotated[int, Field(strict=True, ge=1, le=100)] = 20,
    ) -> dict[str, Any]:
        """Find definitions by literal name or file-path substring (case-insensitive).

        Returns bounded symbols with kind, qualified name, path, line range and
        lexical parent_id. Empty text lists symbols. truncated signals more matches.
        Does not infer calls, imports, or runtime behavior. Index via the CLI first.
        """
        return query_repository(root, text, limit)

    return server

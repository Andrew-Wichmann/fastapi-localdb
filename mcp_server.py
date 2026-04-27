#!/usr/bin/env python3
"""MCP server wrapping the dev.py CLI for the margin calculator project."""

import subprocess
import sys
from pathlib import Path

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).parent
PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python")
REMOTE_APP_URL = "http://74.208.55.55:8000"
LOCAL_APP_URL = "http://localhost:8000"

mcp = FastMCP("margin-calculator")


def _run(*args: str) -> str:
    result = subprocess.run(
        [PYTHON, "dev.py", *args],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        raise RuntimeError(output)
    return output


@mcp.tool()
def deploy() -> str:
    """Sync local code to the remote server and restart the Docker stack."""
    return _run("deploy")


@mcp.tool()
def pull(
    cob_date: str,
    host: str = REMOTE_APP_URL,
) -> str:
    """Download a SQLite partition from the app for local debugging.

    Args:
        cob_date: Partition date to download (YYYY-MM-DD).
        host: App host to pull from (defaults to remote).
    """
    return _run("pull", cob_date, "--host", host)


@mcp.tool()
def restart(
    remote: bool = False,
    clean: bool = False,
) -> str:
    """Restart the Docker stack locally or on the remote server.

    Args:
        remote: If True, restart the remote stack over SSH.
        clean: If True, remove volumes before restarting (local only).
    """
    args = ["restart"]
    if remote:
        args.append("--remote")
    if clean:
        args.append("--clean")
    return _run(*args)


@mcp.tool()
def replay(
    trace_id: str,
    source: str = REMOTE_APP_URL,
    target: str = LOCAL_APP_URL,
) -> str:
    """Fetch a logged request by trace ID and replay it against a target host.

    Args:
        trace_id: Trace ID of the request to replay.
        source: Host to fetch the original request from (defaults to remote).
        target: Host to replay the request against (defaults to local).
    """
    return _run("replay", trace_id, "--source", source, "--target", target)


if __name__ == "__main__":
    mcp.run()

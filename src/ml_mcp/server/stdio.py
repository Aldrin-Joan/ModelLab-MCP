"""STDIO transport runner for ModelLab FastMCP Server.

Adheres strictly to standard stream discipline:
- stdout: Exclusively reserved for valid MCP JSON-RPC protocol frames.
- stderr: All structured JSON logs, diagnostic output, and trace messages.
"""

import asyncio
import logging
import sys
from ml_mcp.infrastructure.telemetry.logging import configure_logging
from ml_mcp.server.app import create_server

logger = logging.getLogger(__name__)


async def run_stdio_server() -> None:
    """Initialize server components and launch FastMCP STDIO loop."""
    # Strict stream discipline: logs go to stderr ONLY
    configure_logging()
    logger.info("Initializing ModelLab FastMCP server on STDIO transport...")

    server = create_server("ModelLab-STDIO")

    # Run FastMCP stdio server
    await server.run_stdio_async()


def run_stdio() -> None:
    """Synchronous entrypoint for STDIO launcher."""
    try:
        asyncio.run(run_stdio_server())
    except (KeyboardInterrupt, SystemExit):
        sys.stderr.write("ModelLab STDIO server terminated gracefully.\n")
    except Exception as exc:
        sys.stderr.write(f"Fatal error in ModelLab STDIO server: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    run_stdio()

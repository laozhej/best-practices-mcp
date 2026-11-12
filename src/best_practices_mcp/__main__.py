"""Launch the local stdio server."""

import argparse

from best_practices_mcp import __version__
from best_practices_mcp.server import create_server


def main() -> None:
    """Provide CLI metadata and delegate protocol handling to the SDK."""
    parser = argparse.ArgumentParser(
        prog="bestpractices-mcp",
        description="Best Practices MCP: BadgeApp reads, proposals and optional local drafts.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args()
    try:
        server = create_server()
    except ValueError as error:
        parser.error(str(error))
    server.run(transport="stdio")


if __name__ == "__main__":
    main()

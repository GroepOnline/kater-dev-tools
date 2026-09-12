"""MCP transport composition helpers."""

from kater.mcp.product_server import build_product_mcp_app, create_product_server
from kater.mcp.transport import StreamableHttpOnSseMiddleware, combine_mcp_transports

__all__ = [
    "StreamableHttpOnSseMiddleware",
    "build_product_mcp_app",
    "combine_mcp_transports",
    "create_product_server",
]

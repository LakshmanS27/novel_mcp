from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from mcp_server.core.feedback import FeedbackStore
from mcp_server.server.config import get_settings
from mcp_server.server.routes import router
from mcp_server.utils.logger import configure_logging, get_logger


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
if settings.app_host not in _LOOPBACK_HOSTS:
    logger.warning(
        "DLP_MCP_APP_HOST=%s is not a loopback address. This server has no "
        "authentication and exposes local filesystem scanning tools; only "
        "bind to a non-loopback host on a trusted, isolated network.",
        settings.app_host,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = FeedbackStore(settings.db_path)
    await store.initialize()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Risk-aware MCP server for metadata-first DLP analysis.",
    lifespan=lifespan,
)
app.include_router(router)

mcp = FastApiMCP(
    app,
    name="risk_aware_dlp",
    description="Metadata-first DLP analysis exposed as MCP tools.",
)
mcp.mount_http()


def main() -> None:
    uvicorn.run(
        "mcp_server.server.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )

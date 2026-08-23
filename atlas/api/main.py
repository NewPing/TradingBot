"""FastAPI main application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from atlas import __version__
from atlas.api.routers import compare, health, runs, signals, trials, versions
from atlas.core.config import get_settings
from atlas.core.logging import get_logger, setup_logging

logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.atlas_log_level, settings.atlas_log_format)
    logger.info(
        f"Starting ATLAS API v{__version__} [env={settings.atlas_env}, live_allowed={settings.atlas_allow_live}]"
    )
    yield
    logger.info("Stopping ATLAS API")


app = FastAPI(
    title="ATLAS Trading Engine API",
    description="Autonomous Trading & Learning Analysis System",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(versions.router)
app.include_router(runs.router)
app.include_router(compare.router)
app.include_router(trials.router)
app.include_router(signals.router)


@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>ATLAS Trading Engine API</title>
            <style>
                :root {{
                    --bg: #0a0a0a;
                    --bg-sidebar: #0d0d0d;
                    --surface: #141414;
                    --surface-2: #1c1c1c;
                    --active: #1a1a1a;
                    --border: #262626;
                    --border-subtle: #1f1f1f;
                    --text-1: #ededed;
                    --text-2: #a1a1aa;
                    --text-3: #71717a;
                    --pos: #22c55e;
                    --neg: #ef4444;
                    --warn: #f59e0b;
                    --info: #38bdf8;
                }}
                * {{ box-sizing: border-box; margin: 0; padding: 0; }}
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                    background-color: var(--bg);
                    color: var(--text-1);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    padding: 1.5rem;
                }}
                .card {{
                    background-color: var(--surface);
                    border: 1px solid var(--border);
                    border-radius: 8px;
                    padding: 2.25rem;
                    max-width: 520px;
                    width: 100%;
                    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
                }}
                .badge-status {{
                    display: inline-flex;
                    align-items: center;
                    gap: 0.5rem;
                    background-color: var(--surface-2);
                    color: var(--pos);
                    border: 1px solid var(--border);
                    padding: 0.3rem 0.75rem;
                    border-radius: 6px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    letter-spacing: 0.05em;
                    text-transform: uppercase;
                    margin-bottom: 1.25rem;
                    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                }}
                .status-dot {{
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background-color: var(--pos);
                    box-shadow: 0 0 8px var(--pos);
                }}
                h1 {{
                    font-size: 1.5rem;
                    font-weight: 600;
                    letter-spacing: -0.02em;
                    color: var(--text-1);
                    margin-bottom: 0.5rem;
                }}
                p {{
                    color: var(--text-2);
                    font-size: 0.925rem;
                    line-height: 1.55;
                    margin-bottom: 1.5rem;
                }}
                .meta-label {{
                    font-size: 0.7rem;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    color: var(--text-3);
                    margin-bottom: 0.75rem;
                    font-weight: 600;
                    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                }}
                ul {{ list-style: none; display: flex; flex-direction: column; gap: 0.5rem; }}
                a {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 0.75rem 1rem;
                    background-color: var(--surface-2);
                    color: var(--text-1);
                    text-decoration: none;
                    border: 1px solid var(--border);
                    border-radius: 6px;
                    font-size: 0.875rem;
                    font-weight: 500;
                    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                    transition: all 0.15s ease-in-out;
                }}
                a:hover {{
                    background-color: var(--active);
                    border-color: var(--pos);
                    color: var(--text-1);
                }}
                a .arrow {{
                    color: var(--text-3);
                    font-size: 0.8rem;
                    transition: transform 0.15s ease-in-out;
                }}
                a:hover .arrow {{
                    color: var(--pos);
                    transform: translateX(3px);
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="badge-status">
                    <span class="status-dot"></span>
                    <span>System Online · Port 8001</span>
                </div>
                <h1>ATLAS Engine API v{__version__}</h1>
                <p>Autonomous Trading &amp; Learning Analysis System backend service.</p>
                <div class="meta-label">Developer Endpoints</div>
                <ul>
                    <li><a href="/docs"><span>Interactive Swagger UI (/docs)</span><span class="arrow">&rarr;</span></a></li>
                    <li><a href="/health"><span>System Health Check JSON (/health)</span><span class="arrow">&rarr;</span></a></li>
                    <li><a href="/version"><span>System Version Info JSON (/version)</span><span class="arrow">&rarr;</span></a></li>
                </ul>
            </div>
        </body>
    </html>
    """

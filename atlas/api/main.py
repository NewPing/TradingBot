"""FastAPI main application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from atlas import __version__
from atlas.api.routers import (
    compare,
    fundamentals,
    health,
    live,
    models,
    news,
    research,
    risk,
    runs,
    signals,
    trials,
    versions,
)
from atlas.api.ws import ws_manager
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

    try:
        from pathlib import Path

        from atlas.data.db import get_engine, get_session_factory
        from atlas.data.models import Base
        from atlas.ml.bootstrap import bootstrap_default_lgbm_model
        from atlas.strategies.registry import StrategyVersionRegistry

        Base.metadata.create_all(get_engine())
        factory = get_session_factory()
        with factory() as session:
            reg = StrategyVersionRegistry(session)
            reg.sync_directory(Path("strategies"))

        # Ensure default baseline ML model is ready
        bootstrap_default_lgbm_model()
    except Exception as exc:
        logger.warning(f"Database/Model auto-init notice: {exc}")

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
app.include_router(live.router)
app.include_router(risk.router)
app.include_router(models.router)
app.include_router(fundamentals.router)
app.include_router(news.router)
app.include_router(research.router)


@app.websocket("/api/v1/ws/live")
async def websocket_live_endpoint(websocket: WebSocket) -> None:
    """Real-time streaming endpoint for live runner events, fills, blotter, and alerts."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep-alive loop
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except Exception:
        pass
    finally:
        ws_manager.disconnect(websocket)


@app.get("/", response_class=HTMLResponse)
def root_status_page() -> str:
    """Developer / Terminal Dark Theme API Root Splash Page."""
    settings = get_settings()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ATLAS Engine API v{__version__}</title>
  <style>
    :root {{
      --bg: #0a0a0a;
      --bg-sidebar: #0d0d0d;
      --surface: #141414;
      --surface-2: #1c1c1c;
      --border: #262626;
      --border-subtle: #1f1f1f;
      --text-1: #ededed;
      --text-2: #a1a1aa;
      --text-3: #71717a;
      --pos: #22c55e;
      --neg: #ef4444;
      --warn: #f59e0b;
      --info: #38bdf8;
      --font-mono: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background-color: var(--bg);
      color: var(--text-1);
      font-family: var(--font-mono);
      font-size: 13px;
      line-height: 1.5;
      padding: 32px;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{
      max-width: 860px;
      margin: 0 auto;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding-bottom: 20px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }}
    h1 {{
      font-size: 18px;
      font-weight: 600;
      letter-spacing: -0.02em;
      color: var(--text-1);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 2px;
      background: var(--surface-2);
      border: 1px solid var(--border);
      color: var(--text-2);
    }}
    .dot {{
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--pos);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 2px;
      padding: 16px;
    }}
    .card-title {{
      color: var(--text-3);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}
    .card-value {{
      font-size: 14px;
      font-weight: 500;
      color: var(--text-1);
    }}
    .routes {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 2px;
      padding: 20px;
    }}
    .routes-title {{
      font-size: 12px;
      font-weight: 600;
      color: var(--text-2);
      margin-bottom: 12px;
      border-bottom: 1px solid var(--border-subtle);
      padding-bottom: 6px;
    }}
    ul {{
      list-style: none;
    }}
    li {{
      padding: 6px 0;
      display: flex;
      justify-content: space-between;
      border-bottom: 1px solid var(--border-subtle);
    }}
    li:last-child {{
      border-bottom: none;
    }}
    a {{
      color: var(--info);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .method {{
      color: var(--text-3);
      font-size: 11px;
    }}
    footer {{
      margin-top: 32px;
      font-size: 11px;
      color: var(--text-3);
      display: flex;
      justify-content: space-between;
      border-top: 1px solid var(--border-subtle);
      padding-top: 16px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <h1>ATLAS Engine API</h1>
        <div style="color: var(--text-3); font-size: 12px; margin-top: 4px;">Autonomous Quantitative Trading & Risk Daemon</div>
      </div>
      <div class="badge">
        <span class="dot"></span>
        <span>ONLINE</span>
      </div>
    </header>

    <div class="grid">
      <div class="card">
        <div class="card-title">Version & Engine</div>
        <div class="card-value">v{__version__} · Python 3.12</div>
      </div>
      <div class="card">
        <div class="card-title">Environment & Gate</div>
        <div class="card-value">{settings.atlas_env.upper()} · LIVE={str(settings.atlas_allow_live).upper()}</div>
      </div>
      <div class="card">
        <div class="card-title">Storage Backend</div>
        <div class="card-value">TimescaleDB + Redis + Parquet</div>
      </div>
    </div>

    <div class="routes">
      <div class="routes-title">CORE API ENDPOINTS</div>
      <ul>
        <li><a href="/docs">/docs (Interactive Swagger UI)</a><span class="method">UI</span></li>
        <li><a href="/health">/health</a><span class="method">GET</span></li>
        <li><a href="/api/v1/versions">/api/v1/versions</a><span class="method">GET, POST</span></li>
        <li><a href="/api/v1/runs">/api/v1/runs</a><span class="method">GET, POST</span></li>
        <li><a href="/api/v1/compare">/api/v1/compare</a><span class="method">GET, POST</span></li>
        <li><a href="/api/v1/trials">/api/v1/trials</a><span class="method">GET</span></li>
        <li><a href="/api/v1/signals/explore?symbol=SPY">/api/v1/signals/explore</a><span class="method">GET</span></li>
        <li><a href="/api/v1/live/state">/api/v1/live/state</a><span class="method">GET</span></li>
        <li><a href="/api/v1/risk/status">/api/v1/risk/status</a><span class="method">GET, POST</span></li>
        <li><a href="/api/v1/models">/api/v1/models</a><span class="method">GET</span></li>
        <li><a href="/api/v1/models/regime/current">/api/v1/models/regime/current</a><span class="method">GET</span></li>
        <li><a href="/api/v1/research/status">/api/v1/research/status</a><span class="method">GET, POST</span></li>
        <li><a href="/api/v1/research/reports">/api/v1/research/reports</a><span class="method">GET</span></li>
        <li><span>/api/v1/ws/live</span><span class="method">WSS</span></li>
      </ul>
    </div>

    <footer>
      <span>ATLAS v{__version__}</span>
      <span>Strict UTC · Invariant-Checked</span>
    </footer>
  </div>
</body>
</html>
"""

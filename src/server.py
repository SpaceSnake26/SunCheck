"""FastAPI server for SunCheck bot dashboard."""
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Query, Path
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
import asyncio
import re
from bot_service import BotService
import uvicorn
import os


# =============================================================================
# PYDANTIC VALIDATION MODELS
# =============================================================================

class TradeApprovalRequest(BaseModel):
    """Request model for trade approval."""
    amount: float = Field(
        default=20.0,
        ge=1.0,
        le=1000.0,
        description="Trade amount in USD (1-1000)"
    )


class FilterUpdateRequest(BaseModel):
    """Request model for filter updates."""
    min_edge: float = Field(
        ge=0.0,
        le=1.0,
        description="Minimum edge threshold (0-1)"
    )
    max_days: float = Field(
        ge=0.0,
        le=30.0,
        description="Maximum days to settlement (0-30)"
    )


class StatusResponse(BaseModel):
    """Generic status response."""
    status: str
    message: Optional[str] = None


class TradeResponse(BaseModel):
    """Response model for trade operations."""
    status: str
    message: str


class ModeResponse(BaseModel):
    """Response model for mode toggle."""
    status: str
    mode: str


def validate_uuid(trade_id: str) -> str:
    """
    Validate that trade_id looks like a UUID.
    
    Raises HTTPException if invalid.
    """
    uuid_pattern = re.compile(
        r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$',
        re.IGNORECASE
    )
    if not uuid_pattern.match(trade_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trade_id format: {trade_id}"
        )
    return trade_id


# =============================================================================
# APPLICATION SETUP
# =============================================================================

# Initialize Bot
bot = BotService()

# Background task reference
_scheduler_task = None

import threading

async def run_in_daemon_thread(func, *args):
    """Run a blocking function in a daemon thread."""
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def wrapper():
        try:
            result = func(*args)
            loop.call_soon_threadsafe(future.set_result, result)
        except Exception as e:
            loop.call_soon_threadsafe(future.set_exception, e)

    threading.Thread(target=wrapper, daemon=True).start()
    return await future

async def scheduler():
    """Runs the bot every hour."""
    while True:
        # Sleep for 1 hour
        await asyncio.sleep(3600)
        # Run in daemon thread to ensure Ctrl+C works
        if bot.run_status != "Running":
            await run_in_daemon_thread(bot.run_cycle)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    global _scheduler_task
    # Startup: Start background scheduler
    _scheduler_task = asyncio.create_task(scheduler())
    bot.log("Background scheduler started.")
    yield
    # Shutdown: Cancel scheduler task
    # Shutdown: Cancel scheduler task
    yield
    # Shutdown: IMMEDIATE EXIT
    # We skip all cleanup to prevent hangs. The OS will clean up resources.
    print("Shutdown signal received. Force killing process now.")
    os._exit(0)

# Aggressive Exit Handler to prevent hangs
import signal
import sys
import threading
import time

def shutdown_watchdog():
    """Background thread to force kill process if it hangs."""
    print("Shutdown watchdog started. Force exit in 1.0s...")
    time.sleep(1.0)
    print("Watchdog: Force exiting now.")
    os._exit(0)

def force_exit(signum, frame):
    print(f"\nSignal {signum} received. Scheduling force exit...")
    # Start watchdog thread to ensure we die even if main loop is stuck
    t = threading.Thread(target=shutdown_watchdog, daemon=True)
    t.start()
    
    # Also try to kill immediately if possible, but yield to let Uvicorn print its log
    # raising SystemExit might trigger Uvicorn's cleanup, which we want to bypass if it hangs
    # So we just let the watchdog do it, or fall through to lifespan

# Register signal handlers
signal.signal(signal.SIGINT, force_exit)
signal.signal(signal.SIGTERM, force_exit)

app = FastAPI(title="SunCheck Bot Dashboard", lifespan=lifespan)

# Setup Templates and Static Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    context = bot.get_context()
    context["request"] = request
    return templates.TemplateResponse("index.html", context)

@app.get("/api/logs", response_class=HTMLResponse)
async def get_logs(request: Request):
    context = {"logs": bot.logs, "request": request}
    return templates.TemplateResponse("logs_partial.html", context)


@app.get("/api/opportunities", response_class=HTMLResponse)
async def get_opportunities(request: Request):
    """Lightweight endpoint for opportunities polling - skips heavy portfolio calculations."""
    # Get only the opportunities data with minimal processing
    proposed_trades = bot.get_opportunities_fast()
    context = {
        "proposed_trades": proposed_trades,
        "request": request
    }
    return templates.TemplateResponse("opportunities_partial.html", context)


@app.get("/api/status")
async def get_status():
    """Fast status endpoint for smart polling."""
    return {
        "status": bot.run_status,
        "proposals_count": len(bot.proposed_trades),
        "last_run": bot.last_run
    }


@app.get("/api/run", response_model=StatusResponse)
async def run_now():
    """Manually trigger a bot scan cycle."""
    if bot.run_status == "Running":
        return StatusResponse(status="skipped", message="Bot is already running")
    asyncio.create_task(manual_run())
    return StatusResponse(status="triggered", message="Scan cycle started")

@app.post("/api/trade/{trade_id}/approve", response_model=TradeResponse)
async def approve_trade(
    trade_id: str = Path(..., description="UUID of the trade to approve"),
    amount: float = Form(
        default=20.0,
        ge=1.0,
        le=1000.0,
        description="Trade amount in USD"
    )
):
    """Approve and execute a proposed trade."""
    validate_uuid(trade_id)
    success, msg = bot.approve_trade(trade_id, amount)
    return TradeResponse(
        status="success" if success else "error",
        message=msg
    )

@app.post("/api/trade/{trade_id}/reject", response_model=TradeResponse)
async def reject_trade(
    trade_id: str = Path(..., description="UUID of the trade to reject")
):
    """Reject a proposed trade."""
    validate_uuid(trade_id)
    success = bot.reject_trade(trade_id)
    return TradeResponse(
        status="success" if success else "error",
        message="Rejected" if success else "Trade not found"
    )

@app.get("/api/reset", response_model=StatusResponse)
async def reset_bot():
    """Manually reset the bot status to Idle."""
    bot.run_status = "Idle"
    bot.log("Bot status manually reset to Idle.")
    return StatusResponse(status="reset", message="Bot status reset to Idle")
    
@app.post("/api/toggle_mode", response_model=ModeResponse)
async def toggle_mode():
    """Toggle between LIVE and PAPER trading modes."""
    bot.live_mode = not bot.live_mode
    mode_str = "LIVE" if bot.live_mode else "PAPER"
    bot.log(f"Switched to {mode_str} Trading Mode")
    return ModeResponse(status="success", mode=mode_str)

@app.post("/api/filters", response_model=StatusResponse)
async def update_filters(
    min_edge: float = Form(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum edge threshold"
    ),
    max_days: float = Form(
        ...,
        ge=0.0,
        le=30.0,
        description="Maximum days to settlement"
    )
):
    """Update dashboard filter settings."""
    bot.min_edge = min_edge
    bot.max_settle_days = max_days
    bot.log(f"Filters updated: Min Edge {min_edge:.2%}, Max Days {max_days}")
    return StatusResponse(status="success")

async def manual_run():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, bot.run_cycle)


if __name__ == "__main__":
    print("Starting Uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

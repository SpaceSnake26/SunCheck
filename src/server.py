from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from bot_service import BotService
import uvicorn
import os

app = FastAPI(title="SunCheck Bot Dashboard")

# Initialize Bot
bot = BotService()

# Setup Templates and Static Files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

@app.on_event("startup")
async def startup_event():
    # Start background loop
    asyncio.create_task(scheduler())

async def scheduler():
    """Runs the bot every hour."""
    while True:
        # Sleep for 1 hour
        await asyncio.sleep(3600)
        # Run in thread pool to avoid blocking event loop
        if bot.run_status != "Running":
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, bot.run_cycle)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    context = bot.get_context()
    context["request"] = request
    return templates.TemplateResponse("index.html", context)

@app.get("/api/logs", response_class=HTMLResponse)
async def get_logs(request: Request):
    context = {"logs": bot.logs, "request": request}
    return templates.TemplateResponse("logs_partial.html", context)

@app.get("/api/run")
async def run_now():
    """Manual trigger."""
    asyncio.create_task(manual_run())
    return {"status": "Triggered"}

@app.post("/api/trade/{trade_id}/approve")
async def approve_trade(trade_id: str, amount: float = 20.0):
    success, msg = bot.approve_trade(trade_id, amount)
    return {"status": "success" if success else "error", "message": msg}

@app.post("/api/trade/{trade_id}/reject")
async def reject_trade(trade_id: str):
    bot.reject_trade(trade_id)
    return {"status": "success", "message": "Rejected"}

@app.get("/api/reset")
async def reset_bot():
    """Manually reset the bot status."""
    bot.run_status = "Idle"
    bot.log("Bot status manually reset to Idle.")
    return {"status": "Reset"}
    
@app.post("/api/toggle_mode")
async def toggle_mode():
    bot.live_mode = not bot.live_mode
    mode_str = "LIVE" if bot.live_mode else "PAPER"
    bot.log(f"Switched to {mode_str} Trading Mode")
    return {"status": "success", "mode": mode_str}

@app.post("/api/filters")
async def update_filters(min_edge: float = Form(...), max_days: float = Form(...)):
    bot.min_edge = min_edge
    bot.max_settle_days = max_days
    bot.log(f"Filters updated: Min Edge {min_edge}, Max Days {max_days}")
    return {"status": "success"}

async def manual_run():
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, bot.run_cycle)


if __name__ == "__main__":
    print("Starting Uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

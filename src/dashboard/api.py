"""
FastAPI dashboard backend.
Provides REST API and WebSocket for the trading dashboard.
"""

from datetime import datetime
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json


app = FastAPI(title="Polymarket Trading Bot Dashboard")

# CORS voor React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Schemas ============

class BotStatus(BaseModel):
    is_running: bool
    is_paused: bool
    pause_reason: Optional[str]
    uptime_seconds: int
    current_balance: float
    session_pnl: float
    session_pnl_pct: float


class TradeStats(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    consecutive_wins: int
    consecutive_losses: int
    total_pnl: float
    best_trade: float
    worst_trade: float


class CurrentPosition(BaseModel):
    market_id: str
    direction: str
    entry_price: float
    current_probability: float
    size_usd: float
    unrealized_pnl: float
    time_remaining_seconds: int


class SettingsUpdate(BaseModel):
    profit_lock_enabled: Optional[bool] = None
    min_confidence: Optional[float] = None
    max_position_pct: Optional[float] = None
    news_pause_enabled: Optional[bool] = None


class TradeRecord(BaseModel):
    id: int
    market_id: str
    direction: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    size_usd: float
    pnl: Optional[float]
    result: Optional[str]
    followed_rules: bool


# ============ REST Endpoints ============

@app.get("/api/status", response_model=BotStatus)
async def get_bot_status():
    """Get current bot status."""
    # TODO: Implementeer met echte bot state
    return BotStatus(
        is_running=True,
        is_paused=False,
        pause_reason=None,
        uptime_seconds=3600,
        current_balance=27.34,
        session_pnl=5.75,
        session_pnl_pct=26.6,
    )


@app.get("/api/stats", response_model=TradeStats)
async def get_trade_stats():
    """Get trading statistics."""
    # TODO: Haal uit database
    return TradeStats(
        total_trades=20,
        winning_trades=16,
        losing_trades=4,
        win_rate=0.80,
        consecutive_wins=3,
        consecutive_losses=0,
        total_pnl=5.75,
        best_trade=3.74,
        worst_trade=-5.00,
    )


@app.get("/api/position", response_model=Optional[CurrentPosition])
async def get_current_position():
    """Get current open position if any."""
    # TODO: Haal uit risk manager
    return None


@app.get("/api/trades", response_model=list[TradeRecord])
async def get_trade_history(
    limit: int = 50,
    offset: int = 0,
    result: Optional[str] = None,
):
    """Get trade history with pagination."""
    # TODO: Query database
    return []


@app.get("/api/settings")
async def get_settings():
    """Get current bot settings."""
    return {
        "profit_lock_enabled": True,
        "profit_lock_threshold": 0.92,
        "min_confidence": 0.80,
        "max_position_pct": 0.05,
        "news_pause_enabled": True,
        "news_pause_duration_seconds": 300,
    }


@app.patch("/api/settings")
async def update_settings(update: SettingsUpdate):
    """Update bot settings."""
    # TODO: Update config en notify bot
    return {"status": "updated", "changes": update.dict(exclude_none=True)}


@app.post("/api/bot/start")
async def start_bot():
    """Start the trading bot."""
    # TODO: Start bot
    return {"status": "started"}


@app.post("/api/bot/stop")
async def stop_bot():
    """Stop the trading bot."""
    # TODO: Stop bot gracefully
    return {"status": "stopped"}


@app.post("/api/bot/pause")
async def pause_bot(duration_minutes: int = 30, reason: str = "Manual pause"):
    """Manually pause the bot."""
    # TODO: Pause bot
    return {"status": "paused", "duration_minutes": duration_minutes}


@app.post("/api/bot/resume")
async def resume_bot():
    """Resume the bot from pause."""
    # TODO: Resume bot
    return {"status": "resumed"}


# ============ WebSocket for Real-time Updates ============

class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Message types:
    - status_update: Bot status changed
    - trade_opened: New trade opened
    - trade_closed: Trade closed
    - position_update: Current position probability updated
    - news_alert: Major news detected
    - pause_started: Bot paused
    - pause_ended: Bot resumed
    """
    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle client commands
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Helper function om updates te broadcasten (wordt aangeroepen door bot)
async def broadcast_update(update_type: str, data: dict):
    """Broadcast an update to all connected clients."""
    await manager.broadcast({
        "type": update_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    })

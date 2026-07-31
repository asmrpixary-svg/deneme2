import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from company.database.connection import get_db, SessionLocal
from company.database.models import Recommendation, ConfigStore, ConfigHistory, Trade, SystemLog
from company.core.events import event_bus
from company.config.settings import settings

app = FastAPI(title="COS XAUUSDT API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

# Setup EventBus listener to pipe event logs directly to WebSocket clients
async def on_log_created(payload: dict):
    await manager.broadcast({
        "type": "log",
        "data": payload
    })

event_bus.subscribe("Log Created", on_log_created)

# Also pipe important side-channel state changes
async def on_session_active(payload: dict):
    await manager.broadcast({"type": "session_active", "data": payload})
async def on_news_blackout(payload: dict):
    await manager.broadcast({"type": "news_blackout", "data": payload})
async def on_low_volatility(payload: dict):
    await manager.broadcast({"type": "low_volatility", "data": payload})
async def on_trade_opened(payload: dict):
    await manager.broadcast({"type": "trade_opened", "data": payload})
async def on_trade_closed(payload: dict):
    await manager.broadcast({"type": "trade_closed", "data": payload})

event_bus.subscribe("Session Active", on_session_active)
event_bus.subscribe("News Blackout Active", on_news_blackout)
event_bus.subscribe("Low Volatility Regime", on_low_volatility)
event_bus.subscribe("Trade Opened", on_trade_opened)
event_bus.subscribe("Trade Closed", on_trade_closed)

@app.on_event("startup")
async def startup_event():
    # Instantiate and start all background departments
    from company.departments.market import MarketDepartment
    from company.departments.technical import TechnicalDepartment
    from company.departments.strategy import StrategyDepartment
    from company.departments.risk import RiskDepartment
    from company.departments.trade import TradeDepartment
    from company.departments.portfolio import PortfolioDepartment
    from company.departments.learning import LearningDepartment
    from company.departments.backtest import BacktestDepartment
    from company.departments.scheduler import SchedulerDepartment
    from company.departments.news import NewsDepartment
    from company.departments.monitoring import MonitoringDepartment

    app.state.departments = {
        "market": MarketDepartment(),
        "technical": TechnicalDepartment(),
        "strategy": StrategyDepartment(),
        "risk": RiskDepartment(),
        "trade": TradeDepartment(),
        "portfolio": PortfolioDepartment(),
        "learning": LearningDepartment(),
        "backtest": BacktestDepartment(),
        "scheduler": SchedulerDepartment(),
        "news": NewsDepartment(),
        "monitoring": MonitoringDepartment()
    }

    for dept_name, dept_obj in app.state.departments.items():
        asyncio.create_task(dept_obj.start())

@app.get("/config")
def get_config(db: Session = Depends(get_db)):
    rows = db.query(ConfigStore).all()
    return {r.key: r.value for r in rows}

@app.get("/recommendations")
def get_recommendations(db: Session = Depends(get_db)):
    return db.query(Recommendation).all()

@app.post("/recommendations/{id}/approve")
async def approve_recommendation(id: str, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = "approved"
    rec.resolved_at = datetime.utcnow()

    # Apply to ConfigStore
    cfg = db.query(ConfigStore).filter(ConfigStore.key == rec.target_param).first()
    old_val = cfg.value if cfg else None

    if cfg:
        cfg.value = rec.suggested_value
    else:
        db.add(ConfigStore(key=rec.target_param, value=rec.suggested_value))

    # Save to history trail
    history = ConfigHistory(
        key=rec.target_param,
        old_value=old_val,
        new_value=rec.suggested_value,
        source=rec.source
    )
    db.add(history)
    db.commit()

    # Broadcast event so departments reload dynamically
    await event_bus.publish("Config Updated", {
        "key": rec.target_param,
        "new_value": rec.suggested_value,
        "old_value": old_val
    })

    # Push update to WebSockets
    await manager.broadcast({
        "type": "config_updated",
        "data": {
            "key": rec.target_param,
            "value": rec.suggested_value
        }
    })

    return {"status": "success", "recommendation_id": id}

@app.post("/recommendations/{id}/reject")
def reject_recommendation(id: str, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = "rejected"
    rec.resolved_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "recommendation_id": id}

@app.get("/config/history")
def get_config_history(db: Session = Depends(get_db)):
    return db.query(ConfigHistory).order_by(ConfigHistory.timestamp.desc()).all()

@app.post("/config/rollback/{id}")
async def rollback_config(id: int, db: Session = Depends(get_db)):
    hist = db.query(ConfigHistory).filter(ConfigHistory.id == id).first()
    if not hist:
        raise HTTPException(status_code=404, detail="History record not found")

    # Restore old value
    cfg = db.query(ConfigStore).filter(ConfigStore.key == hist.key).first()
    if cfg:
        cfg.value = hist.old_value
        db.commit()

        # Log manual restoration
        rollback_record = ConfigHistory(
            key=hist.key,
            old_value=hist.new_value,
            new_value=hist.old_value,
            source="manually_restored"
        )
        db.add(rollback_record)
        db.commit()

        # Broadcast config updated
        await event_bus.publish("Config Updated", {
            "key": hist.key,
            "new_value": hist.old_value,
            "old_value": hist.new_value
        })

        await manager.broadcast({
            "type": "config_updated",
            "data": {
                "key": hist.key,
                "value": hist.old_value
            }
        })

        return {"status": "success", "restored": hist.key, "value": hist.old_value}

    raise HTTPException(status_code=500, detail="Unable to rollback")

@app.get("/trades")
def get_trades(db: Session = Depends(get_db)):
    return db.query(Trade).order_by(Trade.created_at.desc()).all()

@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    trades = db.query(Trade).all()
    if not trades:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "total_trades": 0,
            "balance": 100.0,
            "slippage": 0.0,
            "commission": 0.0
        }

    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    win_rate = len(wins) / len(trades) if trades else 0.0
    total_win_pnl = sum([t.pnl for t in wins])
    total_loss_pnl = abs(sum([t.pnl for t in losses]))

    profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else total_win_pnl
    avg_win = total_win_pnl / len(wins) if wins else 0.0
    avg_loss = total_loss_pnl / len(losses) if losses else 1.0
    expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)

    total_comm = sum([t.commission for t in trades])
    total_pnl = sum([t.pnl for t in trades]) - total_comm

    return {
        "win_rate": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "total_trades": len(trades),
        "balance": round(100.0 + total_pnl, 2),
        "slippage": round(sum([t.slippage for t in trades]) / len(trades), 4) if trades else 0.0,
        "commission": round(total_comm, 2)
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state dump
        db = SessionLocal()
        logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).limit(50).all()
        log_dump = [
            {
                "id": l.id,
                "department": l.department,
                "level": l.level,
                "message": l.message,
                "timestamp": l.timestamp.isoformat()
            } for l in logs
        ]

        await websocket.send_json({
            "type": "init_logs",
            "data": log_dump
        })
        db.close()

        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

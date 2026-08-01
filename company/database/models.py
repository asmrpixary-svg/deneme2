from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from datetime import datetime
from company.database.connection import Base

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, default="XAUUSDT")
    direction = Column(String)  # LONG, SHORT
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float)
    status = Column(String, default="OPEN")  # OPEN, CLOSED
    mode = Column(String)  # PAPER, BACKTEST, LIVE_MICRO
    strategy_version_id = Column(String)  # Strategy version tracking
    pnl = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    active_filters = Column(Text, default="[]")  # JSON list of filters active at entry
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

class ConfigStore(Base):
    __tablename__ = "config_store"

    key = Column(String, primary_key=True, index=True)
    value = Column(String)  # JSON or text representations of values
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ConfigHistory(Base):
    __tablename__ = "config_history"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String)
    old_value = Column(String)
    new_value = Column(String)
    source = Column(String)  # learning_dept, backtest_dept, manually_restored
    timestamp = Column(DateTime, default=datetime.utcnow)

class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(String, primary_key=True, index=True)
    source = Column(String)  # learning_dept, backtest_dept
    target_param = Column(String)
    current_value = Column(Text)
    suggested_value = Column(Text)
    reason = Column(Text)
    confidence_score = Column(Float)
    sample_size = Column(Integer)
    status = Column(String, default="pending")  # pending, approved, rejected
    run_id = Column(String, nullable=True)  # link to ablation or walk-forward run
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String)
    level = Column(String)
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

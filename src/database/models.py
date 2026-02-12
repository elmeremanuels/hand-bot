"""
SQLAlchemy database models voor de trading bot.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship, declarative_base
from enum import Enum


Base = declarative_base()


class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TradeResult(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class Trade(Base):
    """Individuele trade record."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)

    # Market info
    market_id = Column(String(255), nullable=False, index=True)
    token_id = Column(String(255), nullable=False)
    direction = Column(String(10), nullable=False)  # "up" or "down"

    # Entry
    entry_price = Column(Float, nullable=False)
    entry_confidence = Column(Float, nullable=False)
    entry_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    size_usd = Column(Float, nullable=False)
    size_shares = Column(Float, nullable=False)

    # Market state at entry
    btc_price_at_entry = Column(Float)
    btc_target_price = Column(Float)
    time_remaining_at_entry = Column(Integer)  # seconds

    # Exit
    exit_price = Column(Float)
    exit_time = Column(DateTime)
    exit_reason = Column(String(100))  # "expiry", "profit_lock", "manual"

    # Result
    status = Column(SQLEnum(TradeStatus), default=TradeStatus.PENDING)
    result = Column(SQLEnum(TradeResult))
    pnl = Column(Float)
    pnl_percentage = Column(Float)

    # Analysis
    followed_rules = Column(Boolean, default=True)
    rule_violations = Column(JSON)  # List of violated rules
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    news_context = relationship("TradeNewsContext", back_populates="trade")


class TradeNewsContext(Base):
    """Nieuws context voor een trade."""

    __tablename__ = "trade_news_context"

    id = Column(Integer, primary_key=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=False)

    news_id = Column(String(255))
    news_title = Column(Text)
    news_source = Column(String(100))
    news_sentiment = Column(String(20))
    news_impact = Column(String(20))

    # Market reaction analysis
    market_reaction = Column(String(20))  # "as_expected", "opposite", "neutral"

    trade = relationship("Trade", back_populates="news_context")


class NewsEvent(Base):
    """Gelogde nieuwsevents."""

    __tablename__ = "news_events"

    id = Column(Integer, primary_key=True)

    external_id = Column(String(255), unique=True)
    title = Column(Text, nullable=False)
    source = Column(String(100))
    url = Column(Text)
    published_at = Column(DateTime, nullable=False)

    # Analysis
    sentiment = Column(String(20))
    impact = Column(String(20))
    keywords_matched = Column(JSON)

    # Market reaction
    btc_price_at_publish = Column(Float)
    btc_price_after_5min = Column(Float)
    btc_price_change_pct = Column(Float)
    market_reaction = Column(String(20))

    # Did we pause?
    triggered_pause = Column(Boolean, default=False)
    pause_duration_seconds = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeEntry(Base):
    """
    Kennisdatabase entry.
    Slaat geleerde patronen en inzichten op.
    """

    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True)

    # Categorisatie
    category = Column(String(50), nullable=False)  # "news_reaction", "pattern", "rule_performance"
    subcategory = Column(String(50))

    # Content
    title = Column(String(255), nullable=False)
    description = Column(Text)
    data = Column(JSON)  # Flexible data storage

    # Relevantie
    confidence_score = Column(Float, default=0.5)  # Hoe betrouwbaar is dit inzicht?
    sample_size = Column(Integer, default=1)  # Op hoeveel observaties gebaseerd?
    last_validated = Column(DateTime)

    # Recency weighting
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status
    is_active = Column(Boolean, default=True)
    manually_reviewed = Column(Boolean, default=False)


class BotSession(Base):
    """Bot sessie tracking."""

    __tablename__ = "bot_sessions"

    id = Column(Integer, primary_key=True)

    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime)

    # Balance
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float)

    # Stats
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0.0)

    # Config snapshot
    config_snapshot = Column(JSON)

    # Status
    is_active = Column(Boolean, default=True)
    end_reason = Column(String(100))  # "manual", "error", "scheduled"


class DailyStats(Base):
    """Dagelijkse statistieken."""

    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True)
    date = Column(DateTime, nullable=False, unique=True)

    # Trading stats
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float)

    # P&L
    gross_pnl = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)  # After fees

    # Balance
    starting_balance = Column(Float)
    ending_balance = Column(Float)

    # Market conditions
    btc_price_open = Column(Float)
    btc_price_close = Column(Float)
    btc_volatility = Column(Float)

    # News
    major_news_events = Column(Integer, default=0)
    pause_count = Column(Integer, default=0)
    total_pause_duration_seconds = Column(Integer, default=0)

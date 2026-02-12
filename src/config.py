"""
Configuratie module voor de Polymarket trading bot.
Alle settings worden geladen uit environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class PolymarketConfig(BaseSettings):
    """Polymarket API configuratie."""

    # API Credentials
    api_key: Optional[str] = Field(default=None, env="POLYMARKET_API_KEY")
    private_key: Optional[str] = Field(default=None, env="POLYMARKET_PRIVATE_KEY")

    # API Endpoints
    clob_host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"

    # Chain config
    chain_id: int = 137  # Polygon mainnet


class TradingConfig(BaseSettings):
    """Trading strategie configuratie."""

    # Entry criteria
    min_confidence: float = Field(default=0.80, ge=0.50, le=0.99, env="MIN_CONFIDENCE")
    max_confidence: float = Field(default=0.95, ge=0.80, le=0.99, env="MAX_CONFIDENCE")
    min_time_remaining_seconds: int = Field(default=60, ge=30, env="MIN_TIME_REMAINING")
    max_time_remaining_seconds: int = Field(default=180, le=300, env="MAX_TIME_REMAINING")
    min_expected_edge: float = Field(default=0.10, ge=0.05, env="MIN_EXPECTED_EDGE")

    # Position sizing - SAFETY LIMITS
    max_position_size: float = Field(default=5.0, ge=1.0, le=50.0, env="MAX_POSITION_SIZE")  # Max $5 per trade
    max_open_positions: int = Field(default=3, ge=1, le=10, env="MAX_OPEN_POSITIONS")
    max_total_exposure: float = Field(default=15.0, env="MAX_TOTAL_EXPOSURE")  # 3 positions * $5

    # Risk management
    max_consecutive_losses: int = Field(default=3)
    pause_after_losses_minutes: int = Field(default=30)

    # Profit lock
    profit_lock_enabled: bool = True
    profit_lock_threshold: float = Field(default=0.92, ge=0.85, le=0.99)

    # Volatility adjustments
    high_volatility_min_confidence: float = Field(default=0.85)


class NewsConfig(BaseSettings):
    """Nieuws monitoring configuratie."""

    # API Keys
    cryptonews_api_key: Optional[str] = Field(default=None, env="CRYPTONEWS_API_KEY")
    coinfeeds_api_key: Optional[str] = Field(default=None, env="COINFEEDS_API_KEY")
    twitter_bearer_token: Optional[str] = Field(default=None, env="TWITTER_BEARER_TOKEN")

    # News pause settings
    pause_on_major_news: bool = True
    news_pause_duration_seconds: int = Field(default=300, ge=60, le=600)  # 5 min default

    # Keywords die een pause triggeren
    major_news_keywords: list[str] = [
        "SEC", "ETF", "ban", "hack", "crash", "surge", "regulation",
        "Binance", "Coinbase", "Fed", "interest rate", "inflation",
        "Elon Musk", "MicroStrategy", "halving", "fork"
    ]


class DatabaseConfig(BaseSettings):
    """Database configuratie."""

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/polymarket_bot",
        env="DATABASE_URL"
    )

    # Knowledge base settings
    knowledge_recency_weight: float = Field(default=0.7)  # Hoe zwaar recente data weegt
    max_knowledge_entries: int = Field(default=10000)


class DashboardConfig(BaseSettings):
    """Dashboard configuratie."""

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # WebSocket
    ws_heartbeat_interval: int = 30


class NotificationConfig(BaseSettings):
    """Notificatie configuratie."""

    telegram_bot_token: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, env="TELEGRAM_CHAT_ID")

    # Wat te notificeren
    notify_on_trade: bool = True
    notify_on_loss: bool = True
    notify_on_news_pause: bool = True
    notify_on_error: bool = True


class Settings(BaseSettings):
    """Hoofdconfiguratie die alle sub-configs combineert."""

    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # Paper trading mode (geen echte trades)
    paper_trading: bool = Field(default=True, env="PAPER_TRADING")

    # Bot settings
    scan_interval_seconds: int = Field(default=10, ge=5, le=60, env="SCAN_INTERVAL_SECONDS")
    target_asset: Optional[str] = Field(default=None, env="TARGET_ASSET")  # bitcoin, ethereum, solana, xrp

    # Convenience accessors for nested configs
    @property
    def polymarket_api_key(self) -> Optional[str]:
        return self.polymarket.api_key

    @property
    def polymarket_private_key(self) -> Optional[str]:
        return self.polymarket.private_key

    @property
    def max_position_size(self) -> float:
        return self.trading.max_position_size

    @property
    def max_open_positions(self) -> int:
        return self.trading.max_open_positions

    @property
    def max_total_exposure(self) -> float:
        return self.trading.max_total_exposure

    @property
    def min_confidence(self) -> float:
        return self.trading.min_confidence

    @property
    def max_confidence(self) -> float:
        return self.trading.max_confidence

    # Sub-configurations
    polymarket: PolymarketConfig = PolymarketConfig()
    trading: TradingConfig = TradingConfig()
    news: NewsConfig = NewsConfig()
    database: DatabaseConfig = DatabaseConfig()
    dashboard: DashboardConfig = DashboardConfig()
    notifications: NotificationConfig = NotificationConfig()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()

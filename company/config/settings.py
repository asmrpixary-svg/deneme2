import os
from cryptography.fernet import Fernet

class Settings:
    # General Configs
    PROJECT_NAME: str = "Company Operating System (COS)"
    VERSION: str = "1.0.0"

    # Mode configurations
    # Can be PAPER, BACKTEST, LIVE_MICRO
    TRADE_MODE: str = os.getenv("TRADE_MODE", "PAPER")

    # Live trading switch
    CONFIRM_LIVE_TRADING: bool = os.getenv("CONFIRM_LIVE_TRADING", "false").lower() == "true"
    LIVE_TEST_CAPITAL: float = 100.0

    # Symbol Config
    ACTIVE_SYMBOL: str = "XAUUSDT"

    # XAUUSDT Specific Configurations (Binance Futures)
    XAUUSDT_ATR_MULTIPLIER: float = 1.2  # Dynamic ATR multiplier within 1.0 - 1.5 range
    XAUUSDT_LEVERAGE: int = 3            # Safe leverage (3x - 5x)
    XAUUSDT_RSI_PERIOD: int = 14
    XAUUSDT_RSI_OVERBOUGHT: float = 70.0
    XAUUSDT_RSI_OVERSOLD: float = 30.0
    XAUUSDT_EMA_FAST: int = 50
    XAUUSDT_EMA_SLOW: int = 200

    # Session / Liquidity settings
    SESSION_FILTER_ASIA_ENABLED: bool = False
    SESSION_FILTER_LONDON_ENABLED: bool = True
    SESSION_FILTER_NY_ENABLED: bool = True

    # Confluence config
    MIN_CONFLUENCE_COUNT: int = 3

    # News Blackout Window (Minutes)
    NEWS_BLACKOUT_WINDOW_MINS: int = 30

    # Drawdown Circuit Breakers (Percentages)
    DAILY_LOSS_LIMIT_PCT: float = 5.0
    WEEKLY_LOSS_LIMIT_PCT: float = 10.0

    # Low Volatility Regime
    LOW_VOLATILITY_THRESHOLD: float = 1.5  # If ATR goes below this, filter activates

    # Support/Resistance margin
    SR_PROXIMITY_MARGIN_PCT: float = 0.1  # Do not enter if current price is within 0.1% of key S/R

    # Partial Fill Strategy (CANCEL or WAIT)
    PARTIAL_FILL_STRATEGY: str = "CANCEL"

    # Dynamic durable key getter
    @classmethod
    def get_or_create_encryption_key(cls) -> bytes:
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            return env_key.encode() if isinstance(env_key, str) else env_key
        key_path = "company/config/.encryption_key"
        if os.path.exists(key_path):
            try:
                with open(key_path, "rb") as f:
                    return f.read()
            except Exception:
                pass
        new_key = Fernet.generate_key()
        try:
            with open(key_path, "wb") as f:
                f.write(new_key)
        except Exception:
            pass
        return new_key

    # Encryption key for API Key rotation / storage
    ENCRYPTION_KEY: bytes = b""

    # API key rotation intervals (simulated logic / config)
    API_KEY_ROTATION_DAYS: int = 30

    @classmethod
    def encrypt_api_key(cls, val: str) -> str:
        key = cls.get_or_create_encryption_key()
        f = Fernet(key)
        return f.encrypt(val.encode()).decode()

    @classmethod
    def decrypt_api_key(cls, val: str) -> str:
        key = cls.get_or_create_encryption_key()
        f = Fernet(key)
        return f.decrypt(val.encode()).decode()

settings = Settings()

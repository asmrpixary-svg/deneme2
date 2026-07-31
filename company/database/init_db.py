import json
from company.database.connection import engine, SessionLocal
from company.database.models import Base, ConfigStore
from company.config.settings import settings

def init_db():
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Initialize default config store values from settings
    db = SessionLocal()
    try:
        defaults = {
            "xauusdt_atr_multiplier": str(settings.XAUUSDT_ATR_MULTIPLIER),
            "xauusdt_leverage": str(settings.XAUUSDT_LEVERAGE),
            "session_filter.asia_enabled": str(settings.SESSION_FILTER_ASIA_ENABLED).lower(),
            "session_filter.london_enabled": str(settings.SESSION_FILTER_LONDON_ENABLED).lower(),
            "session_filter.ny_enabled": str(settings.SESSION_FILTER_NY_ENABLED).lower(),
            "min_confluence_count": str(settings.MIN_CONFLUENCE_COUNT),
            "news_blackout_window_mins": str(settings.NEWS_BLACKOUT_WINDOW_MINS),
            "daily_loss_limit_pct": str(settings.DAILY_LOSS_LIMIT_PCT),
            "weekly_loss_limit_pct": str(settings.WEEKLY_LOSS_LIMIT_PCT),
            "low_volatility_threshold": str(settings.LOW_VOLATILITY_THRESHOLD),
            "sr_proximity_margin_pct": str(settings.SR_PROXIMITY_MARGIN_PCT),
            "partial_fill_strategy": settings.PARTIAL_FILL_STRATEGY,
            "confirm_live_trading": str(settings.CONFIRM_LIVE_TRADING).lower()
        }

        for key, val in defaults.items():
            existing = db.query(ConfigStore).filter(ConfigStore.key == key).first()
            if not existing:
                db.add(ConfigStore(key=key, value=val))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error initializing database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")

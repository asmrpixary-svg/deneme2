import asyncio
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class StrategyDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Strategy Dept")
        # Multi-filter states from yan kanallar (side-channels)
        self.session_active = "LONDON"  # Active trading session (LONDON, NY, ASIA)
        self.news_blackout_active = False
        self.low_volatility_regime = False

        # S/R key levels configured/detected
        self.key_support = 1950.0
        self.key_resistance = 2100.0

        # Subscribe to side-channel events
        event_bus.subscribe("Indicators Calculated", self.on_indicators_calculated)
        event_bus.subscribe("Session Active", self.on_session_active)
        event_bus.subscribe("News Blackout Active", self.on_news_blackout_active)
        event_bus.subscribe("Low Volatility Regime", self.on_low_volatility_regime)

    async def start(self):
        self.logger.info("Strategy Department has started.")
        await self._reload_config()

    async def _reload_config(self):
        self.min_confluence_count = int(self.get_config_value("min_confluence_count", "3"))
        self.sr_proximity_margin_pct = float(self.get_config_value("sr_proximity_margin_pct", "0.1"))
        self.asia_enabled = self.get_config_value("session_filter.asia_enabled", "false") == "true"
        self.london_enabled = self.get_config_value("session_filter.london_enabled", "true") == "true"
        self.ny_enabled = self.get_config_value("session_filter.ny_enabled", "true") == "true"
        self.logger.info(f"Loaded config: min_confluence={self.min_confluence_count}, SR proximity margin={self.sr_proximity_margin_pct}")

    async def on_session_active(self, payload: dict):
        self.session_active = payload.get("session", "LONDON").upper()

    async def on_news_blackout_active(self, payload: dict):
        self.news_blackout_active = payload.get("active", False)

    async def on_low_volatility_regime(self, payload: dict):
        self.low_volatility_regime = True

    async def on_indicators_calculated(self, payload: dict):
        # Reset low volatility if not triggered in payload
        self.low_volatility_regime = payload.get("is_low_volatility", False)

        price = payload["price"]
        ema_fast = payload["ema_fast"]
        ema_slow = payload["ema_slow"]
        rsi = payload["rsi"]
        market_structure = payload["market_structure"]

        # 1. Base trend direction signal
        # LONG if EMA_Fast > EMA_Slow, SHORT if EMA_Fast < EMA_Slow
        direction = "LONG" if ema_fast > ema_slow else "SHORT"

        # 2. Confluence Evaluation
        confluence_count = 0
        active_filters = []

        # Filter A: Trend & Market Structure match
        if direction == "LONG" and market_structure == "BULLISH":
            confluence_count += 1
            active_filters.append("Market Structure Bullish")
        elif direction == "SHORT" and market_structure == "BEARISH":
            confluence_count += 1
            active_filters.append("Market Structure Bearish")

        # Filter B: Momentum match (RSI)
        if direction == "LONG" and rsi < 65:  # Not overbought yet
            confluence_count += 1
            active_filters.append("RSI Safe Long")
        elif direction == "SHORT" and rsi > 35:  # Not oversold yet
            confluence_count += 1
            active_filters.append("RSI Safe Short")

        # Filter C: Base EMA direction
        if (direction == "LONG" and price > ema_fast) or (direction == "SHORT" and price < ema_fast):
            confluence_count += 1
            active_filters.append("EMA Alignment")

        # Filter D: Session restrictions
        session_allowed = True
        if self.session_active == "ASIA" and not self.asia_enabled:
            session_allowed = False
        elif self.session_active == "LONDON" and not self.london_enabled:
            session_allowed = False
        elif self.session_active == "NY" and not self.ny_enabled:
            session_allowed = False

        if not session_allowed:
            self.logger.warning(f"Signal Rejected: Session Filter ({self.session_active} disabled)")
            return

        # Filter E: Low Volatility Regime check
        if self.low_volatility_regime:
            self.logger.warning("Signal Rejected: Volatility Regime Filter (Low Volatility detected)")
            return

        # Filter F: S/R Order Block proximity filter
        # If we are too close to key S/R levels, entry should be delayed/cancelled
        dist_support = abs(price - self.key_support) / price
        dist_res = abs(price - self.key_resistance) / price
        if dist_support < self.sr_proximity_margin_pct or dist_res < self.sr_proximity_margin_pct:
            self.logger.warning("Signal Rejected: S/R Proximity confirmation failed")
            return

        # 3. Final verification of Confluence and Signal Emission
        if confluence_count >= self.min_confluence_count:
            # Check strategy version (simple timestamp/hash representation)
            strategy_version = "v1.0.XAU"

            trigger_payload = {
                "symbol": "XAUUSDT",
                "direction": direction,
                "price": price,
                "atr": payload["atr"],
                "active_filters": active_filters,
                "strategy_version_id": strategy_version,
                "timestamp": payload["timestamp"]
            }
            self.logger.info(f"Strategy Triggered: {direction} signal at {price} with confluence count {confluence_count}")
            await event_bus.publish("Strategy Triggered", trigger_payload)
        else:
            # Failed confluence log
            pass

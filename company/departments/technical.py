import asyncio
import collections
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class TechnicalDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Technical Dept")
        self.prices = collections.deque(maxlen=200)
        self.atr_multiplier = 1.2
        self.low_volatility_threshold = 1.5

        # Track highs and lows for market structure detection (HH, HL, LH, LL)
        self.last_highs = collections.deque(maxlen=5)
        self.last_lows = collections.deque(maxlen=5)
        self.market_structure = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL

        event_bus.subscribe("Market Updated", self.on_market_updated)

    async def start(self):
        self.logger.info("Technical Department has started.")
        await self._reload_config()

    async def _reload_config(self):
        self.atr_multiplier = float(self.get_config_value("xauusdt_atr_multiplier", "1.2"))
        self.low_volatility_threshold = float(self.get_config_value("low_volatility_threshold", "1.5"))
        self.logger.info(f"Loaded config: ATR multiplier={self.atr_multiplier}, Low Volatility threshold={self.low_volatility_threshold}")

    async def on_market_updated(self, tick: dict):
        price = tick["price"]
        self.prices.append(price)

        # Skip until we have enough data to calculate simple metrics
        if len(self.prices) < 14:
            return

        # Indicators Calculations
        ema_fast = self.calculate_ema(50)
        ema_slow = self.calculate_ema(200)
        rsi = self.calculate_rsi(14)
        atr = self.calculate_atr(14)

        # Volatility Regime
        is_low_volatility = atr < self.low_volatility_threshold
        if is_low_volatility:
            await event_bus.publish("Low Volatility Regime", {"atr": atr})

        # Detect Market Structure
        self.detect_market_structure(price)

        payload = {
            "symbol": "XAUUSDT",
            "price": price,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "rsi": rsi,
            "atr": atr,
            "market_structure": self.market_structure,
            "is_low_volatility": is_low_volatility,
            "timestamp": tick["timestamp"]
        }

        await event_bus.publish("Indicators Calculated", payload)

    def calculate_ema(self, period: int) -> float:
        if len(self.prices) < period:
            return self.prices[-1]
        # Simplification of EMA
        vals = list(self.prices)[-period:]
        multiplier = 2 / (period + 1)
        ema = vals[0]
        for val in vals[1:]:
            ema = (val - ema) * multiplier + ema
        return ema

    def calculate_rsi(self, period: int) -> float:
        if len(self.prices) < period + 1:
            return 50.0
        gains = []
        losses = []
        vals = list(self.prices)[-(period+1):]
        for i in range(1, len(vals)):
            diff = vals[i] - vals[i-1]
            if diff > 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, period: int) -> float:
        # ATR simplification based on high-low of sliding prices
        if len(self.prices) < period:
            return 2.5
        vals = list(self.prices)[-period:]
        ranges = []
        for i in range(1, len(vals)):
            ranges.append(abs(vals[i] - vals[i-1]))
        if not ranges:
            return 2.5
        return sum(ranges) / len(ranges)

    def detect_market_structure(self, price: float):
        # Peak and trough high-low detection logic
        # If price starts setting Higher Highs & Higher Lows -> BULLISH
        # If Lower Highs & Lower Lows -> BEARISH
        if len(self.prices) < 10:
            return

        vals = list(self.prices)[-10:]
        local_high = max(vals)
        local_low = min(vals)

        if not self.last_highs or local_high != self.last_highs[-1]:
            self.last_highs.append(local_high)
        if not self.last_lows or local_low != self.last_lows[-1]:
            self.last_lows.append(local_low)

        if len(self.last_highs) >= 2 and len(self.last_lows) >= 2:
            hh = self.last_highs[-1] > self.last_highs[-2]
            lh = self.last_highs[-1] < self.last_highs[-2]
            hl = self.last_lows[-1] > self.last_lows[-2]
            ll = self.last_lows[-1] < self.last_lows[-2]

            if hh and hl:
                self.market_structure = "BULLISH"
            elif lh and ll:
                self.market_structure = "BEARISH"
            else:
                self.market_structure = "NEUTRAL"

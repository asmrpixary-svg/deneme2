import asyncio
import collections
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class TechnicalDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Technical Dept")
        # Double-ended queues for different horizons to support Multi-Timeframe (MTF)
        self.prices_5m = collections.deque(maxlen=100)
        self.prices_15m = collections.deque(maxlen=200)
        self.prices_1h = collections.deque(maxlen=400)

        self.atr_multiplier = 1.2
        self.low_volatility_threshold = 1.5

        # Track highs and lows for market structure detection (HH, HL, LH, LL)
        self.last_highs = collections.deque(maxlen=5)
        self.last_lows = collections.deque(maxlen=5)
        self.market_structure = "NEUTRAL"

        event_bus.subscribe("Market Updated", self.on_market_updated)

    async def start(self):
        self.logger.info("Technical Department (MTF Enabled) has started.")
        await self._reload_config()

    async def _reload_config(self):
        self.atr_multiplier = float(self.get_config_value("xauusdt_atr_multiplier", "1.2"))
        self.low_volatility_threshold = float(self.get_config_value("low_volatility_threshold", "1.5"))
        self.logger.info(f"Loaded config: ATR multiplier={self.atr_multiplier}, Low Volatility threshold={self.low_volatility_threshold}")

    async def on_market_updated(self, tick: dict):
        price = tick["price"]

        # Append to different timeframes
        self.prices_5m.append(price)
        self.prices_15m.append(price)
        self.prices_1h.append(price)

        if len(self.prices_15m) < 14:
            return

        # 1. 15m Base Indicators
        ema_fast_15m = self.calculate_ema(self.prices_15m, 50)
        ema_slow_15m = self.calculate_ema(self.prices_15m, 200)
        rsi_15m = self.calculate_rsi(self.prices_15m, 14)
        atr_15m = self.calculate_atr(self.prices_15m, 14)

        # 2. Multi-Timeframe Alignment Check (5m and 1h)
        ema_fast_5m = self.calculate_ema(self.prices_5m, 20)
        ema_slow_5m = self.calculate_ema(self.prices_5m, 50)
        rsi_5m = self.calculate_rsi(self.prices_5m, 14)

        ema_fast_1h = self.calculate_ema(self.prices_1h, 100)
        ema_slow_1h = self.calculate_ema(self.prices_1h, 300)
        rsi_1h = self.calculate_rsi(self.prices_1h, 14)

        # MTF Trend Alignment Flag
        mtf_bullish = (ema_fast_5m > ema_slow_5m) and (ema_fast_15m > ema_slow_15m) and (ema_fast_1h > ema_slow_1h)
        mtf_bearish = (ema_fast_5m < ema_slow_5m) and (ema_fast_15m < ema_slow_15m) and (ema_fast_1h < ema_slow_1h)
        mtf_alignment = "BULLISH" if mtf_bullish else "BEARISH" if mtf_bearish else "NEUTRAL"

        # Volatility Regime
        is_low_volatility = atr_15m < self.low_volatility_threshold
        if is_low_volatility:
            await event_bus.publish("Low Volatility Regime", {"atr": atr_15m})

        # Detect Market Structure (HH/HL or LH/LL)
        self.detect_market_structure(price)

        payload = {
            "symbol": "XAUUSDT",
            "price": price,
            "ema_fast": ema_fast_15m,
            "ema_slow": ema_slow_15m,
            "rsi": rsi_15m,
            "atr": atr_15m,
            "market_structure": self.market_structure,
            "is_low_volatility": is_low_volatility,
            "mtf_alignment": mtf_alignment,
            "rsi_5m": rsi_5m,
            "rsi_1h": rsi_1h,
            "timestamp": tick["timestamp"],
            # Include book imbalance if present in tick
            "order_book_imbalance": tick.get("order_book_imbalance", 0.0)
        }

        await event_bus.publish("Indicators Calculated", payload)

    def calculate_ema(self, queue, period: int) -> float:
        if len(queue) < period:
            return queue[-1] if queue else 2000.0
        vals = list(queue)[-period:]
        multiplier = 2 / (period + 1)
        ema = vals[0]
        for val in vals[1:]:
            ema = (val - ema) * multiplier + ema
        return ema

    def calculate_rsi(self, queue, period: int) -> float:
        if len(queue) < period + 1:
            return 50.0
        gains = []
        losses = []
        vals = list(queue)[-(period+1):]
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

    def calculate_atr(self, queue, period: int) -> float:
        if len(queue) < period:
            return 2.5
        vals = list(queue)[-period:]
        ranges = []
        for i in range(1, len(vals)):
            ranges.append(abs(vals[i] - vals[i-1]))
        if not ranges:
            return 2.5
        return sum(ranges) / len(ranges)

    def detect_market_structure(self, price: float):
        if len(self.prices_15m) < 10:
            return

        vals = list(self.prices_15m)[-10:]
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

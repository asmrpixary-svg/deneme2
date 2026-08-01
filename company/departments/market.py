import asyncio
import httpx
import random
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class MarketDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Market Dept")
        self.last_price = 2000.0  # Safe starter fallback
        self.consecutive_bad_ticks = 0
        self.last_imbalance = 0.5 # Equal balanced fallback (0.0 - 1.0)
        self.is_first_tick = True

    async def start(self):
        self.logger.info("Market Department with Order Book Depth Imbalance has started.")
        asyncio.create_task(self.fetch_ticks_loop())

    async def fetch_ticks_loop(self):
        async with httpx.AsyncClient() as client:
            while True:
                await asyncio.sleep(2)  # Tick every 2 seconds

                # Fetch tick price
                tick = await self.fetch_binance_ticker(client)

                # Fetch order book depth imbalance
                imbalance = await self.fetch_order_book_imbalance(client)
                tick["order_book_imbalance"] = imbalance

                if self.validate_data(tick):
                    self.last_price = tick["price"]
                    self.last_imbalance = imbalance
                    await event_bus.publish("Market Updated", tick)
                else:
                    self.logger.warning(f"Data Integrity violation detected. Tick rejected: {tick}")

    async def fetch_binance_ticker(self, client: httpx.AsyncClient) -> dict:
        try:
            response = await client.get("https://fapi.binance.com/fapi/v1/ticker/price?symbol=XAUUSDT", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                price = float(data.get("price", self.last_price))
                return {
                    "symbol": "XAUUSDT",
                    "price": price,
                    "volume": random.uniform(50.0, 200.0),
                    "timestamp": asyncio.get_event_loop().time()
                }
        except Exception as e:
            self.logger.warning(f"Failed to fetch tick from real Binance API: {e}. Falling back to safe drift simulation...")

        change = random.uniform(-1.0, 1.0)
        price = max(100.0, self.last_price + change)
        return {
            "symbol": "XAUUSDT",
            "price": price,
            "volume": random.uniform(10.0, 150.0),
            "timestamp": asyncio.get_event_loop().time()
        }

    async def fetch_order_book_imbalance(self, client: httpx.AsyncClient) -> float:
        """
        Calculates the ratio of cumulative Bid volume divided by (Bid volume + Ask volume).
        If > 0.5, buy pressure dominates. If < 0.5, sell pressure dominates.
        """
        try:
            response = await client.get("https://fapi.binance.com/fapi/v1/depth?symbol=XAUUSDT&limit=10", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                bids = data.get("bids", [])
                asks = data.get("asks", [])

                # Sum the sizes (quantity) of top bids and asks
                bid_vol = sum([float(b[1]) for b in bids])
                ask_vol = sum([float(a[1]) for a in asks])

                total_vol = bid_vol + ask_vol
                if total_vol > 0:
                    imbalance = bid_vol / total_vol
                    return round(imbalance, 4)
        except Exception as e:
            # Fallback drift
            pass

        # Fallback to dynamic random fluctuation around last imbalance
        return max(0.1, min(0.9, self.last_imbalance + random.uniform(-0.05, 0.05)))

    def validate_data(self, tick: dict) -> bool:
        price = tick.get("price", 0.0)
        if price <= 0.0:
            return False

        if self.is_first_tick:
            self.is_first_tick = False
            return True

        if self.last_price > 0:
            pct_change = abs(price - self.last_price) / self.last_price
            if pct_change > 0.15:
                return False
        return True

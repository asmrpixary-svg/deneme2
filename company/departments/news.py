import asyncio
import random
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class NewsDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("News Dept")

    async def start(self):
        self.logger.info("News Department has started.")
        asyncio.create_task(self.macro_calendar_poll_loop())

    async def macro_calendar_poll_loop(self):
        while True:
            # Simulates high-impact news event schedule checks (T-30 / T+30)
            # Forex Factory / FRED API / Investing.com macro calendar scrapers
            if random.random() < 0.05:  # 5% chance of upcoming high-impact event
                self.logger.warning("HIGH IMPACT NEWS DETECTED (CPI/FOMC). Initiating News Blackout active window (T-30 to T+30).")
                await event_bus.publish("News Blackout Active", {"active": True})

                # Blackout runs for 30s in our accelerated simulator
                await asyncio.sleep(30)
                self.logger.info("News Blackout active window ended. Resume normal risk tolerance.")
                await event_bus.publish("News Blackout Active", {"active": False})

            await asyncio.sleep(15)

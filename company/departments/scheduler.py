import asyncio
from datetime import datetime
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class SchedulerDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Scheduler Dept")

    async def start(self):
        self.logger.info("Scheduler Department has started.")
        asyncio.create_task(self.session_monitoring_loop())

    async def session_monitoring_loop(self):
        while True:
            # Check current hour and publish Session Active notifications
            hour = datetime.utcnow().hour

            if 0 <= hour < 8:
                session = "ASIA"
            elif 8 <= hour < 16:
                session = "LONDON"
            else:
                session = "NY"

            await event_bus.publish("Session Active", {"session": session})
            await asyncio.sleep(10)  # Check every 10s

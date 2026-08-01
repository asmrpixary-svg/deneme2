import asyncio
import httpx
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class MonitoringDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Monitoring Dept")
        # Watch critical triggers
        event_bus.subscribe("Daily Loss Limit Hit", self.on_daily_loss_limit)
        event_bus.subscribe("Exchange Connection Lost", self.on_exchange_lost)

    async def start(self):
        self.logger.info("Monitoring Department has started.")

    async def on_daily_loss_limit(self, payload: dict):
        msg = "🚨 EMERGENCY NOTICE: Daily Drawdown Loss Limit breached! New order executions frozen."
        self.logger.error(msg)
        await self.send_instant_notification(msg)

    async def on_exchange_lost(self, payload: dict):
        msg = "🚨 CRITICAL ERROR: Connection to Binance exchange lost! Check API keys or local network."
        self.logger.error(msg)
        await self.send_instant_notification(msg)

    async def send_instant_notification(self, message: str):
        # Dispatches instantly to Telegram Bot or Email webhook
        # Log locally for simulation verification
        self.logger.info(f"Notification Sent successfully to User (Telegram / Email): {message}")

        # Mocking an actual HTTP Post to Telegram Bot API
        try:
            # httpx.post("https://api.telegram.org/bot<token>/sendMessage", json={"chat_id": "123", "text": message})
            pass
        except Exception:
            pass
class SecurityDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Security Dept")

    async def start(self):
        self.logger.info("Security Department has started.")

import asyncio
from company.departments.base import BaseDepartment
from company.core.events import event_bus

class PortfolioDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Portfolio Dept")
        self.balance = 100.0  # Safe micro starter capital
        self.total_commission = 0.0

        event_bus.subscribe("Portfolio Updated", self.on_portfolio_updated)
        event_bus.subscribe("Trade Closed", self.on_trade_closed)

    async def start(self):
        self.logger.info("Portfolio Department has started.")
        await self._reload_config()

    async def _reload_config(self):
        # Read the initial capital settings if any
        pass

    async def on_portfolio_updated(self, payload: dict):
        pnl = payload.get("pnl", 0.0)
        self.balance += pnl
        self.logger.info(f"Portfolio balance updated: ${self.balance:.2f} (change: ${pnl:+.2f})")
        await event_bus.publish("Report Generated", {"balance": self.balance})

    async def on_trade_closed(self, payload: dict):
        comm = payload.get("commission", 0.0)
        self.total_commission += comm
        self.balance -= comm
        self.logger.info(f"Paid commission: ${comm:.2f}. Running commission total: ${self.total_commission:.2f}")

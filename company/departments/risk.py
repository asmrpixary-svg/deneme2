import asyncio
from datetime import datetime, timedelta
from company.departments.base import BaseDepartment
from company.core.events import event_bus
from company.database.connection import SessionLocal
from company.database.models import Trade

class RiskDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Risk Dept")
        self.news_blackout_active = False
        self.daily_loss_limit_hit = False
        self.weekly_loss_limit_hit = False

        self.daily_limit_pct = 5.0
        self.weekly_limit_pct = 10.0

        event_bus.subscribe("Strategy Triggered", self.on_strategy_triggered)
        event_bus.subscribe("News Blackout Active", self.on_news_blackout_active)

    async def start(self):
        self.logger.info("Risk Department has started.")
        await self._reload_config()
        asyncio.create_task(self.circuit_breaker_monitoring_loop())

    async def _reload_config(self):
        self.daily_limit_pct = float(self.get_config_value("daily_loss_limit_pct", "5.0"))
        self.weekly_limit_pct = float(self.get_config_value("weekly_loss_limit_pct", "10.0"))
        self.logger.info(f"Loaded config: Daily loss limit={self.daily_limit_pct}%, Weekly loss limit={self.weekly_limit_pct}%")

    async def on_news_blackout_active(self, payload: dict):
        self.news_blackout_active = payload.get("active", False)

    async def on_strategy_triggered(self, payload: dict):
        self.logger.info(f"Evaluating Risk for {payload['direction']} entry at {payload['price']}")

        if self.news_blackout_active:
            self.logger.warning("Risk Denied: News Blackout is currently active.")
            return

        if self.daily_loss_limit_hit:
            self.logger.warning("Risk Denied: Daily Loss Limit Hit circuit breaker active.")
            await event_bus.publish("Daily Loss Limit Hit", {"time": datetime.utcnow().isoformat()})
            return

        if self.weekly_loss_limit_hit:
            self.logger.warning("Risk Denied: Weekly Loss Limit Hit circuit breaker active.")
            return

        price = payload["price"]
        atr = payload["atr"]
        atr_multiplier = float(self.get_config_value("xauusdt_atr_multiplier", "1.2"))
        leverage = int(self.get_config_value("xauusdt_leverage", "3"))

        stop_distance = atr * atr_multiplier
        risk_per_trade_pct = 0.01

        capital = 100.0
        allowed_risk_amount = capital * risk_per_trade_pct

        qty = allowed_risk_amount / stop_distance
        qty = round(qty, 2)
        if qty <= 0:
            qty = 0.01

        notional_value = qty * price
        max_notional_allowed = capital * leverage

        if notional_value > max_notional_allowed:
            qty = round(max_notional_allowed / price, 2)
            notional_value = qty * price

        if qty <= 0:
            self.logger.warning("Risk Denied: Calculated trade quantity is zero.")
            return

        approved_payload = {
            **payload,
            "quantity": qty,
            "stop_loss_dist": stop_distance,
            "notional": notional_value,
            "timestamp": asyncio.get_event_loop().time()
        }

        self.logger.info(f"Risk Approved: Entry approved. Qty={qty}, SL Distance={stop_distance:.2f}")
        await event_bus.publish("Risk Approved", approved_payload)

    async def circuit_breaker_monitoring_loop(self):
        while True:
            await self.check_drawdown_limits()
            await asyncio.sleep(10)

    async def check_drawdown_limits(self):
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            # Sum up closed trade net PnLs
            daily_trades = db.query(Trade).filter(Trade.closed_at >= day_ago).all()
            net_daily_pnl = sum([t.pnl - t.commission for t in daily_trades])
            daily_loss_pct = abs((net_daily_pnl / 100.0) * 100.0) if net_daily_pnl < 0 else 0.0

            weekly_trades = db.query(Trade).filter(Trade.closed_at >= week_ago).all()
            net_weekly_pnl = sum([t.pnl - t.commission for t in weekly_trades])
            weekly_loss_pct = abs((net_weekly_pnl / 100.0) * 100.0) if net_weekly_pnl < 0 else 0.0

            if daily_loss_pct >= self.daily_limit_pct:
                if not self.daily_loss_limit_hit:
                    self.logger.error("CIRCUIT BREAKER: Daily loss limit hit. Disabling new positions.")
                    self.daily_loss_limit_hit = True
            else:
                self.daily_loss_limit_hit = False

            if weekly_loss_pct >= self.weekly_limit_pct:
                if not self.weekly_loss_limit_hit:
                    self.logger.error("CIRCUIT BREAKER: Weekly loss limit hit. Disabling new positions.")
                    self.weekly_loss_limit_hit = True
            else:
                self.weekly_loss_limit_hit = False
        except Exception as e:
            self.logger.error(f"Error checking drawdown limits: {e}")
        finally:
            db.close()

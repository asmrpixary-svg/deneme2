import asyncio
import random
from datetime import datetime
from company.departments.base import BaseDepartment
from company.core.events import event_bus
from company.database.connection import SessionLocal
from company.database.models import Trade

class TradeDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Trade Dept")
        self.exchange_connected = True
        self.open_trades = {}

        event_bus.subscribe("Risk Approved", self.on_risk_approved)
        event_bus.subscribe("Exchange Connection Lost", self.on_connection_lost)

    async def start(self):
        self.logger.info("Trade Department has started.")
        await self._reload_config()
        # Mock exchange order check loop for TP/SL trigger checks
        asyncio.create_task(self.exchange_monitoring_loop())

    async def _reload_config(self):
        self.trade_mode = self.get_config_value("trade_mode", "PAPER")
        self.confirm_live = self.get_config_value("confirm_live_trading", "false") == "true"
        self.partial_fill_strategy = self.get_config_value("partial_fill_strategy", "CANCEL")

    async def on_connection_lost(self, payload: dict):
        self.exchange_connected = False
        self.logger.error("ALERT: Exchange connection lost! Safeguards initiated. Positions will be managed via local OCO rules.")

    async def on_risk_approved(self, payload: dict):
        # Enforce LIVE_MICRO requirements if configured
        if self.trade_mode == "LIVE_MICRO" and not self.confirm_live:
            self.logger.error("LIVE_MICRO Trade Denied: Live trading confirmation flag is missing or false in config!")
            return

        if not self.exchange_connected:
            self.logger.error("Trade Rejected: Unable to send orders while exchange connection is down.")
            return

        # Perform Binance API call with backoff retry logic
        success = await self.execute_order_with_backoff(payload)
        if not success:
            self.logger.error("Order Execution failed after repeated retries due to rate limit or connection issue.")
            return

        # Record trade in DB
        db = SessionLocal()
        try:
            # Handle partial fill check simulator
            filled_qty = payload["quantity"]
            if random.random() < 0.05:  # 5% chance of partial fill
                if self.partial_fill_strategy == "CANCEL":
                    self.logger.warning("Partial Fill strategy: CANCEL. Cancelling remainder of order.")
                    filled_qty = round(payload["quantity"] * 0.5, 2)
                else:
                    self.logger.info("Partial Fill strategy: WAIT. Waiting for full order fill.")

            t = Trade(
                symbol=payload["symbol"],
                direction=payload["direction"],
                entry_price=payload["price"],
                quantity=filled_qty,
                status="OPEN",
                mode=self.trade_mode,
                strategy_version_id=payload["strategy_version_id"],
                active_filters=str(payload["active_filters"])
            )
            db.add(t)
            db.commit()
            db.refresh(t)

            self.open_trades[t.id] = {
                "db_id": t.id,
                "entry_price": t.entry_price,
                "direction": t.direction,
                "quantity": t.quantity,
                "stop_loss": t.entry_price - payload["stop_loss_dist"] if t.direction == "LONG" else t.entry_price + payload["stop_loss_dist"],
                "take_profit": t.entry_price + (payload["stop_loss_dist"] * 2) if t.direction == "LONG" else t.entry_price - (payload["stop_loss_dist"] * 2)
            }

            self.logger.info(f"Trade Opened: {t.direction} {t.quantity} {t.symbol} at {t.entry_price}. SL: {self.open_trades[t.id]['stop_loss']:.2f}, TP: {self.open_trades[t.id]['take_profit']:.2f}")
            await event_bus.publish("Trade Opened", {"trade_id": t.id, "direction": t.direction, "entry_price": t.entry_price})
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error persisting opened trade: {e}")
        finally:
            db.close()

    async def execute_order_with_backoff(self, payload: dict) -> bool:
        # Exponential backoff retry simulator
        retries = 3
        delay = 1.0
        for i in range(retries):
            try:
                # Simulate potential rate limiting
                if random.random() < 0.1:
                    raise Exception("Binance API Rate Limit Exceeded (429)")
                return True
            except Exception as e:
                self.logger.warning(f"Execution try {i+1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 2.0
        return False

    async def exchange_monitoring_loop(self):
        while True:
            await asyncio.sleep(5)
            # Fetch last known price
            db = SessionLocal()
            try:
                from company.departments.market import MarketDepartment
                # Fetch random price move
                for tid, trade in list(self.open_trades.items()):
                    # Simulate price check on exchange
                    current_price = trade["entry_price"] + random.uniform(-10.0, 10.0)

                    sl = trade["stop_loss"]
                    tp = trade["take_profit"]

                    triggered = False
                    pnl = 0.0

                    if trade["direction"] == "LONG":
                        if current_price <= sl:
                            triggered = True
                            pnl = (sl - trade["entry_price"]) * trade["quantity"]
                        elif current_price >= tp:
                            triggered = True
                            pnl = (tp - trade["entry_price"]) * trade["quantity"]
                    else:
                        if current_price >= sl:
                            triggered = True
                            pnl = (trade["entry_price"] - sl) * trade["quantity"]
                        elif current_price <= tp:
                            triggered = True
                            pnl = (trade["entry_price"] - tp) * trade["quantity"]

                    if triggered:
                        db_trade = db.query(Trade).filter(Trade.id == tid).first()
                        if db_trade:
                            db_trade.status = "CLOSED"
                            db_trade.exit_price = sl if current_price <= sl else tp
                            db_trade.pnl = pnl
                            db_trade.commission = db_trade.quantity * 0.1  # Binance standard futures taker fee
                            db_trade.slippage = random.uniform(0.01, 0.05)
                            db_trade.closed_at = datetime.utcnow()
                            db.commit()

                            self.logger.info(f"Trade Closed: ID {tid}, PnL: {pnl:.2f}, Fee: {db_trade.commission:.2f}, Slip: {db_trade.slippage:.2f}")
                            await event_bus.publish("Trade Closed", {
                                "trade_id": tid,
                                "pnl": pnl,
                                "commission": db_trade.commission,
                                "exit_price": db_trade.exit_price
                            })
                            await event_bus.publish("Portfolio Updated", {"pnl": pnl})

                        self.open_trades.pop(tid, None)
            except Exception as e:
                self.logger.error(f"Error in exchange tracking loop: {e}")
            finally:
                db.close()

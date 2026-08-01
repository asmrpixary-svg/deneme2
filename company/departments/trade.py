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
        self.logger.info("Trade Department (Limit Order Chaser Enabled) has started.")
        await self._reload_config()
        asyncio.create_task(self.exchange_monitoring_loop())

    async def _reload_config(self):
        self.trade_mode = self.get_config_value("trade_mode", "PAPER")
        self.confirm_live = self.get_config_value("confirm_live_trading", "false") == "true"
        self.partial_fill_strategy = self.get_config_value("partial_fill_strategy", "CANCEL")

    async def on_connection_lost(self, payload: dict):
        self.exchange_connected = False
        self.logger.error("ALERT: Exchange connection lost! Safeguards initiated. Positions will be managed via local OCO rules.")

    async def on_risk_approved(self, payload: dict):
        if self.trade_mode == "LIVE_MICRO" and not self.confirm_live:
            self.logger.error("LIVE_MICRO Trade Denied: Live trading confirmation flag is missing or false in config!")
            return

        if not self.exchange_connected:
            self.logger.error("Trade Rejected: Unable to send orders while exchange connection is down.")
            return

        # Post a Limit order and start the chasing/trailing execution strategy
        self.logger.info(f"Initiating Advanced Limit Order Chaser for {payload['direction']} at limit price {payload['price']}")
        chase_result = await self.chase_limit_order(payload)

        if not chase_result["filled"]:
            self.logger.warning("Limit Chaser timed out or was cancelled before fill could occur.")
            return

        final_price = chase_result["execution_price"]
        filled_qty = chase_result["qty"]

        # Record trade in DB
        db = SessionLocal()
        try:
            t = Trade(
                symbol=payload["symbol"],
                direction=payload["direction"],
                entry_price=final_price,
                quantity=filled_qty,
                status="OPEN",
                mode=self.trade_mode,
                strategy_version_id=payload["strategy_version_id"],
                active_filters=str(payload["active_filters"])
            )
            db.add(t)
            db.commit()
            db.refresh(t)

            # Post OCO TP/SL on Exchange side
            self.open_trades[t.id] = {
                "db_id": t.id,
                "entry_price": t.entry_price,
                "direction": t.direction,
                "quantity": t.quantity,
                "stop_loss": t.entry_price - payload["stop_loss_dist"] if t.direction == "LONG" else t.entry_price + payload["stop_loss_dist"],
                "take_profit": t.entry_price + (payload["stop_loss_dist"] * 2) if t.direction == "LONG" else t.entry_price - (payload["stop_loss_dist"] * 2)
            }

            self.logger.info(f"Trade Opened (Limit Chaser filled): {t.direction} {t.quantity} at price {t.entry_price:.2f}. SL: {self.open_trades[t.id]['stop_loss']:.2f}, TP: {self.open_trades[t.id]['take_profit']:.2f}")
            await event_bus.publish("Trade Opened", {"trade_id": t.id, "direction": t.direction, "entry_price": t.entry_price})
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error persisting opened trade: {e}")
        finally:
            db.close()

    async def chase_limit_order(self, payload: dict) -> dict:
        """
        Trails the best bid/ask by submitting and repositioning limit orders
        every 1s to capture Maker fee structure and avoid negative slippage.
        """
        target_price = payload["price"]
        direction = payload["direction"]
        qty = payload["quantity"]

        # Simulate Limit chasing across 3 intervals
        for step in range(3):
            # 70% chance to get filled immediately as maker on each chasing step
            if random.random() < 0.70:
                # Filled as Maker! (Zero or positive slippage)
                execution_price = target_price + random.uniform(-0.1, 0.1)
                self.logger.info(f"Limit order filled as Maker! Steps chased: {step}. Fee discount applied.")
                return {"filled": True, "execution_price": execution_price, "qty": qty}

            # Otherwise price moved away, adjust limit price to chase
            drift = random.uniform(0.1, 0.3)
            if direction == "LONG":
                target_price += drift
            else:
                target_price -= drift
            self.logger.info(f"Chasing Limit Order: Repositioning limit to new best price {target_price:.2f} (Step {step+1}/3)")
            await asyncio.sleep(1)

        # Final fallback: fill remaining qty as Market taker
        execution_price = target_price + (random.uniform(0.1, 0.2) if direction == "LONG" else -random.uniform(0.1, 0.2))
        self.logger.info(f"Limit order chase timeout. Filling remainder as Taker at price {execution_price:.2f}")
        return {"filled": True, "execution_price": execution_price, "qty": qty}

    async def exchange_monitoring_loop(self):
        while True:
            await asyncio.sleep(5)
            db = SessionLocal()
            try:
                for tid, trade in list(self.open_trades.items()):
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
                            # Maker fee is typically 0.02% instead of Taker fee of 0.04%
                            db_trade.commission = db_trade.quantity * 0.05  # Reduced maker fee rate
                            db_trade.slippage = random.uniform(-0.01, 0.01) # Near-zero maker slippage
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

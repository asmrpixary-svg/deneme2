import asyncio
import uuid
import math
from company.departments.base import BaseDepartment
from company.core.events import event_bus
from company.database.connection import SessionLocal
from company.database.models import Trade, Recommendation

class LearningDepartment(BaseDepartment):
    def __init__(self):
        super().__init__("Learning Dept")
        event_bus.subscribe("Trade Closed", self.on_trade_closed)

    async def start(self):
        self.logger.info("Learning Department has started.")
        # Trigger diagnostic updates periodically
        asyncio.create_task(self.nightly_performance_analysis_loop())

    async def on_trade_closed(self, payload: dict):
        # Trigger an immediate calculation scan
        await self.run_performance_scan()

    async def nightly_performance_analysis_loop(self):
        while True:
            await asyncio.sleep(60)  # Check recommendation potential every minute
            await self.run_performance_scan()

    async def run_performance_scan(self):
        db = SessionLocal()
        try:
            trades = db.query(Trade).all()
            if len(trades) < 5:
                return  # Require minimum samples

            wins = [t for t in trades if t.pnl > 0]
            losses = [t for t in trades if t.pnl <= 0]

            win_rate = len(wins) / len(trades) if trades else 0.0

            # Expectancy and Sharpe ratios calculations
            total_win_pnl = sum([t.pnl for t in wins])
            total_loss_pnl = abs(sum([t.pnl for t in losses]))

            profit_factor = total_win_pnl / total_loss_pnl if total_loss_pnl > 0 else total_win_pnl

            avg_win = total_win_pnl / len(wins) if wins else 0.0
            avg_loss = total_loss_pnl / len(losses) if losses else 1.0

            expectancy = (win_rate * avg_win) - ((1.0 - win_rate) * avg_loss)

            # Check for Session Performance suggestions
            # Example: If Asia session performance is terrible (low win rate), write a recommendation
            asia_trades = [t for t in trades if "Session Filter (ASIA" in (t.active_filters or "")]
            # Let's mock a scan that finds low performance and triggers a pending recommendation
            if len(trades) >= 10 and win_rate < 0.45:
                rec_id = f"rec_{uuid.uuid4().hex[:6]}"
                existing = db.query(Recommendation).filter(Recommendation.target_param == "session_filter.asia_enabled").first()
                if not existing or existing.status != "pending":
                    rec = Recommendation(
                        recommendation_id=rec_id,
                        source="learning_dept",
                        target_param="session_filter.asia_enabled",
                        current_value="true",
                        suggested_value="false",
                        reason=f"Asia Session win rate is {win_rate*100:.1f}%, significantly underperforming. Sample size: {len(trades)}",
                        confidence_score=0.85,
                        sample_size=len(trades),
                        status="pending"
                    )
                    db.add(rec)
                    db.commit()
                    self.logger.info(f"New recommendation generated: Disable Asia session (ID: {rec_id})")
        except Exception as e:
            self.logger.error(f"Error running performance scan: {e}")
        finally:
            db.close()

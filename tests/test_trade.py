import pytest
import asyncio
from unittest.mock import AsyncMock
from company.departments.trade import TradeDepartment
from company.core.events import event_bus

@pytest.fixture(autouse=True)
def clean_event_bus():
    event_bus._listeners.clear()
    yield
    event_bus._listeners.clear()

@pytest.mark.asyncio
async def test_live_micro_confirmation_requirement():
    dept = TradeDepartment()
    await dept.start()

    # Set to LIVE_MICRO but without confirmation flag
    dept.trade_mode = "LIVE_MICRO"
    dept.confirm_live = False

    mock_callback = AsyncMock()
    event_bus.subscribe("Trade Opened", mock_callback)

    await event_bus.publish("Risk Approved", {
        "symbol": "XAUUSDT",
        "direction": "LONG",
        "price": 2010.0,
        "quantity": 0.05,
        "stop_loss_dist": 3.0,
        "notional": 100.5,
        "strategy_version_id": "v1.0",
        "active_filters": [],
        "timestamp": 123
    })

    await asyncio.sleep(0.1)
    mock_callback.assert_not_called()

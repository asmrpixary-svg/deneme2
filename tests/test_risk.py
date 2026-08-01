import pytest
import asyncio
from unittest.mock import AsyncMock
from company.departments.risk import RiskDepartment
from company.core.events import event_bus

@pytest.fixture(autouse=True)
def clean_event_bus():
    # Reset listeners before each test to prevent bleed/overlap
    event_bus._listeners.clear()
    yield
    event_bus._listeners.clear()

@pytest.mark.asyncio
async def test_risk_news_blackout():
    dept = RiskDepartment()
    # Avoid starting background loops to prevent race conditions
    await dept._reload_config()

    # Enable news blackout
    dept.news_blackout_active = True

    mock_callback = AsyncMock()
    event_bus.subscribe("Risk Approved", mock_callback)

    await dept.on_strategy_triggered({
        "symbol": "XAUUSDT",
        "direction": "LONG",
        "price": 2010.0,
        "atr": 2.5,
        "active_filters": [],
        "strategy_version_id": "v1.0",
        "timestamp": 123
    })

    await asyncio.sleep(0.1)
    mock_callback.assert_not_called()

@pytest.mark.asyncio
async def test_risk_drawdown_circuit_breaker():
    dept = RiskDepartment()
    await dept._reload_config()

    # Trigger drawdown hit manually
    dept.daily_loss_limit_hit = True

    mock_callback = AsyncMock()
    event_bus.subscribe("Risk Approved", mock_callback)

    await dept.on_strategy_triggered({
        "symbol": "XAUUSDT",
        "direction": "LONG",
        "price": 2010.0,
        "atr": 2.5,
        "active_filters": [],
        "strategy_version_id": "v1.0",
        "timestamp": 123
    })

    await asyncio.sleep(0.1)
    mock_callback.assert_not_called()

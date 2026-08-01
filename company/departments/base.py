from abc import ABC, abstractmethod
from company.core.cos_logging import DepartmentLogger
from company.core.events import event_bus
from company.database.connection import SessionLocal
from company.database.models import ConfigStore
import json

class BaseDepartment(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = DepartmentLogger(name)
        # Subscribe to Config Updates automatically
        event_bus.subscribe("Config Updated", self.on_config_updated)

    @abstractmethod
    async def start(self):
        """Asynchronous startup sequence for department tasks."""
        pass

    async def on_config_updated(self, payload: dict):
        """
        React to live configuration parameter updates pushed from approval system.
        """
        self.logger.info(f"Config updated event received: {payload}")
        await self._reload_config()

    async def _reload_config(self):
        """Reload configuration from SQLite store."""
        pass

    def get_config_value(self, key: str, default: str) -> str:
        db = SessionLocal()
        try:
            cfg = db.query(ConfigStore).filter(ConfigStore.key == key).first()
            if cfg:
                return cfg.value
            return default
        finally:
            db.close()

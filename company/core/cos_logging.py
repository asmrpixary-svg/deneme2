import logging
import asyncio
from datetime import datetime
from company.database.connection import SessionLocal
from company.database.models import SystemLog
from company.core.events import event_bus

class DepartmentLogger:
    def __init__(self, department_name: str):
        self.department_name = department_name
        self.logger = logging.getLogger(department_name)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log(self, level: str, message: str):
        level = level.upper()
        log_msg = f"[{self.department_name}] {message}"
        if level == "INFO":
            self.logger.info(log_msg)
        elif level == "WARNING":
            self.logger.warning(log_msg)
        elif level == "ERROR":
            self.logger.error(log_msg)

        # Async db and event broadcast trigger via dynamic task creation
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            asyncio.create_task(self._persist_and_broadcast(level, message))
        else:
            loop.run_until_complete(self._persist_and_broadcast(level, message))

    async def _persist_and_broadcast(self, level: str, message: str):
        # Persist to SQLite
        db = SessionLocal()
        try:
            sys_log = SystemLog(
                department=self.department_name,
                level=level,
                message=message,
                timestamp=datetime.utcnow()
            )
            db.add(sys_log)
            db.commit()
            db.refresh(sys_log)
            log_id = sys_log.id
        except Exception as e:
            db.rollback()
            print(f"Error persisting log: {e}")
            log_id = None
        finally:
            db.close()

        # Publish dynamic Event update for WebSocket / Dashboard streaming
        await event_bus.publish("Log Created", {
            "id": log_id,
            "department": self.department_name,
            "level": level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })

    def info(self, message: str):
        self.log("INFO", message)

    def warning(self, message: str):
        self.log("WARNING", message)

    def error(self, message: str):
        self.log("ERROR", message)

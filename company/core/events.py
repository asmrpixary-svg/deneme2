import asyncio
import inspect
from typing import Callable, Dict, List, Any

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    async def publish(self, event_type: str, payload: Any = None):
        if event_type not in self._listeners:
            return

        tasks = []
        for callback in self._listeners[event_type]:
            if inspect.iscoroutinefunction(callback):
                tasks.append(callback(payload))
            else:
                # Wrap sync call in executor/task or run directly
                callback(payload)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

event_bus = EventBus()

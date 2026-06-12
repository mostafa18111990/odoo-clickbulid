import logging
from typing import Callable, Dict, List

_logger = logging.getLogger(__name__)

_HANDLERS: Dict[str, List[Callable]] = {}


class EventBusService:
    def __init__(self, env):
        self.env = env

    @classmethod
    def subscribe(cls, event_type, handler):
        _HANDLERS.setdefault(event_type, []).append(handler)
        _logger.debug('EventBus: registered %s for %s', handler.__name__, event_type)

    @classmethod
    def unsubscribe(cls, event_type, handler):
        if event_type in _HANDLERS:
            _HANDLERS[event_type] = [h for h in _HANDLERS[event_type] if h != handler]

    @classmethod
    def get_handlers(cls, event_type):
        return list(_HANDLERS.get(event_type, []))

    def publish(self, event_type, payload=None, model=None, record_id=None, tenant_id=None):
        return self.env['saas.event']._publish(
            event_type=event_type, model=model, record_id=record_id,
            payload=payload or {}, tenant_id=tenant_id)

    def _dispatch(self, event):
        handlers = self.get_handlers(event.event_type)
        if not handlers:
            return
        import json
        try:
            payload = json.loads(event.payload or '{}')
        except (ValueError, TypeError):
            payload = {}
        for handler in handlers:
            try:
                handler(self.env, event, payload)
            except Exception as e:
                _logger.error('EventBus: handler %s failed for %s: %s',
                              handler.__name__, event.event_type, e)

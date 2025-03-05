from typing import Dict, List, Type, Callable, Any
from collections import defaultdict

class EventBus:
    """事件总线，负责事件的发布和订阅"""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件"""
        self.handlers[event_type].append(handler)
        
    def publish(self, event: Any) -> List[Any]:
        """发布事件，返回处理结果列表"""
        event_type = event.event_type
        results = []
        
        for handler in self.handlers.get(event_type, []):
            result = handler(event)
            if result:
                results.extend(result if isinstance(result, list) else [result])
                
        return results

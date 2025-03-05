import asyncio
from typing import Dict, List, Type, Callable, Any
from collections import defaultdict

class EventBus:
    """事件总线，负责事件的发布和订阅"""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件"""
        self.handlers[event_type].append(handler)
        
    async def publish(self, event: Any) -> List[Any]:
        """发布事件，返回处理结果列表"""
        event_type = event.event_type
        results = []
        
        for handler in self.handlers.get(event_type, []):
            if asyncio.iscoroutinefunction(handler):
                result = await handler(event)  # 异步等待异步处理器
            else:
                result = handler(event)  # 同步调用同步处理器
                
            if result:
                results.extend(result if isinstance(result, list) else [result])
                
        return results

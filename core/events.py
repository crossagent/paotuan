import asyncio
import logging
from typing import Dict, List, Type, Callable, Any
from collections import defaultdict

logger = logging.getLogger(__name__)

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
        
        logger.info(f"发布事件: 类型={event_type}, 数据={event.data}")
        
        handlers = self.handlers.get(event_type, [])
        if not handlers:
            logger.warning(f"没有找到事件处理器: 类型={event_type}")
            return results
            
        logger.info(f"找到 {len(handlers)} 个事件处理器: 类型={event_type}")
        
        for handler in handlers:
            handler_name = handler.__name__ if hasattr(handler, "__name__") else str(handler)
            logger.info(f"调用事件处理器: {handler_name}, 事件类型={event_type}")
            
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(event)  # 异步等待异步处理器
                else:
                    result = handler(event)  # 同步调用同步处理器
                    
                if result:
                    if isinstance(result, list):
                        logger.info(f"处理器 {handler_name} 返回 {len(result)} 个结果")
                        results.extend(result)
                    else:
                        logger.info(f"处理器 {handler_name} 返回 1 个结果")
                        results.append(result)
                else:
                    logger.info(f"处理器 {handler_name} 没有返回结果")
            except Exception as e:
                logger.exception(f"事件处理器 {handler_name} 执行失败: {str(e)}")
                
        logger.info(f"事件处理完成: 类型={event_type}, 返回 {len(results)} 个结果")
        return results

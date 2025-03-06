import asyncio
import logging
from typing import Dict, List, Type, Callable, Any, Optional, Union
from collections import defaultdict

logger = logging.getLogger(__name__)

class EventObserver:
    """事件观察者接口"""
    
    async def update(self, event: Any) -> List[Any]:
        """处理事件，返回处理结果列表"""
        raise NotImplementedError("子类必须实现update方法")


class EventBus:
    """事件总线，负责事件的发布和订阅"""
    
    def __init__(self):
        self.observers: Dict[str, List[Union[Callable, EventObserver]]] = defaultdict(list)
        
    def subscribe(self, event_type: str, observer: Union[Callable, EventObserver]) -> None:
        """订阅事件"""
        self.observers[event_type].append(observer)
        
    def unsubscribe(self, event_type: str, observer: Union[Callable, EventObserver]) -> None:
        """取消订阅事件"""
        if event_type in self.observers and observer in self.observers[event_type]:
            self.observers[event_type].remove(observer)
            
    async def publish(self, event: Any) -> List[Any]:
        """发布事件，返回处理结果列表"""
        event_type = event.event_type
        results = []
        
        logger.debug(f"发布事件: 类型={event_type}, 数据={event.data}")
        
        observers = self.observers.get(event_type, [])
        if not observers:
            logger.warning(f"没有找到事件观察者: 类型={event_type}")
            return results
            
        logger.debug(f"找到 {len(observers)} 个事件观察者: 类型={event_type}")
        
        for observer in observers:
            observer_name = self._get_observer_name(observer)
            logger.debug(f"通知事件观察者: {observer_name}, 事件类型={event_type}")
            
            try:
                if isinstance(observer, EventObserver):
                    # 如果是观察者对象，调用其update方法
                    result = await observer.update(event)
                elif asyncio.iscoroutinefunction(observer):
                    # 如果是异步函数，异步等待
                    result = await observer(event)
                else:
                    # 如果是同步函数，同步调用
                    result = observer(event)
                    
                if result:
                    if isinstance(result, list):
                        logger.debug(f"观察者 {observer_name} 返回 {len(result)} 个结果")
                        results.extend(result)
                    else:
                        logger.debug(f"观察者 {observer_name} 返回 1 个结果")
                        results.append(result)
                else:
                    logger.debug(f"观察者 {observer_name} 没有返回结果")
            except Exception as e:
                logger.exception(f"事件观察者 {observer_name} 执行失败: {str(e)}")
                
        logger.debug(f"事件处理完成: 类型={event_type}, 返回 {len(results)} 个结果")
        return results
        
    def _get_observer_name(self, observer: Union[Callable, EventObserver]) -> str:
        """获取观察者名称"""
        if isinstance(observer, EventObserver):
            return observer.__class__.__name__
        elif hasattr(observer, "__name__"):
            return observer.__name__
        else:
            return str(observer)

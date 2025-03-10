import logging
from typing import List, Dict, Any, Optional, Union, Protocol, TypeVar, Type, Generic

from adapters.base import GameEvent

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceProvider(Protocol):
    """服务提供者接口"""
    
    def get_service(self, service_type: Type[T]) -> T:
        """获取指定类型的服务实例"""
        ...

class GameCommand:
    """游戏命令基类
    
    命令模式的实现，负责处理特定类型的事件。
    命令通过服务提供者获取所需的服务，而不是直接依赖于具体实现。
    """
    
    def __init__(self, service_provider: ServiceProvider):
        """初始化命令
        
        Args:
            service_provider: ServiceProvider - 服务提供者，用于获取服务实例
        """
        self.service_provider = service_provider
        
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令，返回事件或消息列表
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        raise NotImplementedError("子类必须实现execute方法")

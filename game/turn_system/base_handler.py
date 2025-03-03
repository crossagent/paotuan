from abc import ABC, abstractmethod
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING, List

if TYPE_CHECKING:
    from game.state.models import Turn, Player, Match

logger = logging.getLogger(__name__)

class TurnHandler(ABC):
    def __init__(self) -> None:
        self.context: Dict[str, Any] = {}  # 存储所有回合相关信息

    def on_enter_turn(self, turn: 'Turn', players: List['Player'], match: 'Match') -> None:
        """当进入新回合时调用"""
        self.context.clear()  # 清除旧上下文
        # 初始化新回合所需的上下文
        self.context['current_turn'] = turn
        self.context['players'] = players
        self.context['match'] = match
        # 其他可能需要的上下文...
        logger.debug(f"{self.__class__.__name__} 进入新回合")

    def get_current_turn(self) -> Optional['Turn']:
        """获取当前回合"""
        return self.context.get('current_turn')

    def on_finish_turn(self) -> None:
        """当回合结束时调用"""
        # 清理资源，执行回合结束时的操作
        logger.debug(f"{self.__class__.__name__} 结束当前回合")

    @abstractmethod
    def handle_event(self, event: Dict[str, Any]) -> None:
        """处理事件"""
        pass

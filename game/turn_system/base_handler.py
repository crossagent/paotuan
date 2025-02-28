from abc import ABC, abstractmethod
from ..state.models import GameMatch
import logging

logger = logging.getLogger(__name__)

class TurnHandler(ABC):
    def __init__(self, game_logic: GameMatch):
        self.game_logic = game_logic
        self._needs_transition = False

    @abstractmethod
    def handle_event(self, event: dict) -> bool:
        """处理事件并返回是否需要状态转换"""
        pass

    def set_needs_transition(self, value: bool):
        """显式设置状态转换标志"""
        self._needs_transition = value
        if value:
            logger.debug(f"{self.__class__.__name__} 请求状态转换")

    @property
    def needs_transition(self) -> bool:
        """检查是否需要执行状态转换"""
        return self._needs_transition

from ..state.models import Match, Room, Turn, InvalidTurnOperation, TurnType, Player  # 添加Player类的导入
from typing import Optional, List  # 添加此行以导入List类型
import logging
from .base_handler import TurnHandler

logger = logging.getLogger(__name__)

class GameMatch:
    def __init__(self):
        self.current_room: Optional[Room] = None
        self.handlers: List[TurnHandler] = []
        self.players: List[Player] = []  # 管理玩家列表

    def add_handler(self, handler: TurnHandler):
        self.handlers.append(handler)

    def create_room(self, room_id: str):
        """创建新房间"""
        if self.current_room:
            raise InvalidGameOperation("已有活跃房间")
        self.current_room = Room(room_id=room_id)
        logger.info(f"房间已创建：{room_id}")

    def destroy_room(self):
        """销毁当前房间"""
        if self.current_room and self.current_room.current_match:
            self.end_match()
        self.current_room = None
        logger.info("房间已销毁")

    def start_match(self, scene: str, players: List[Player]):
        """开始新比赛"""
        if not self.current_room:
            raise InvalidGameOperation("请先创建房间")
        if self.current_room.current_match:
            raise InvalidGameOperation("当前已有进行中的比赛")
            
        self.current_room.create_new_match(scene)
        self.players = players
        for player in players:
            self.current_room.add_player(player)
        logger.info(f"比赛开始 场景：{scene} 玩家数：{len(players)}")

    def end_match(self):
        """结束当前比赛"""
        if not self.current_room or not self.current_room.current_match:
            raise InvalidGameOperation("没有进行中的比赛")
            
        self.current_room.current_match = None
        logger.info("比赛已结束")

    def game_loop(self):
        while True:
            for handler in self.handlers:
                handler.update()
            self._handle_turn_transition()

    def _handle_turn_transition(self):
        """核心回合流转逻辑"""
        if not self.current_room or not self.current_room.current_match:
            return False
            
        current_match = self.current_room.current_match
        if current_match.current_turn and current_match.current_turn.is_completed():
            if current_match.current_turn.turn_type == TurnType.PLAYER:
                return self._start_dm_turn(current_match)
            else:
                return self._start_player_turn(current_match)
        return False

    def _start_dm_turn(self, current_match: Match):
        current_match.start_new_turn(TurnType.DM)
        return True

    def _start_player_turn(self, current_match: Match):
        # 需要外部设置激活玩家逻辑
        if not current_match.current_turn.active_players:
            raise InvalidTurnOperation("激活玩家列表不能为空")
        current_match.start_new_turn(TurnType.PLAYER)
        return True

    def get_current_turn(self) -> Optional[Turn]:
        """获取当前回合"""
        if self.current_room and self.current_room.current_match:
            return self.current_room.current_match.current_turn
        return None

# 新增异常类
class InvalidGameOperation(Exception):
    """非法游戏操作异常"""

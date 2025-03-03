from ..state.models import Match, Room, Turn, InvalidTurnOperation, TurnType, Player  # 添加Player类的导入
from typing import Optional, List  # 添加此行以导入List类型
import logging
from .base_handler import TurnHandler

logger = logging.getLogger(__name__)

class GameMatchLogic:
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

    def process_event(self, event: dict):
        """统一处理游戏事件"""
        result = None
        transition_occurred = False
        
        # 特殊处理强制转换事件
        if event.get('type') == 'force_transition':
            self.handle_turn_transition()
            return "强制执行回合转换"
        
        # 分发事件到各个处理器
        for handler in self.handlers:
            if handler.handle_event(event):
                transition_occurred = True
                
        # 仅当事件处理器明确请求转换时才执行
        if transition_occurred:
            result = self.handle_turn_transition()
            
        return result

    def handle_turn_transition(self):
        """显式处理回合状态转换"""
        if not self.current_room or not self.current_room.current_match:
            logger.warning("当前没有正在进行的比赛")
            return
            
        current_match = self.current_room.current_match
        if current_match.handle_turn_transition():
            logger.info(f"回合转换成功，新回合类型：{current_match.current_turn.turn_type}")
            self._notify_players_of_next_turn()
        else:
            logger.warning("回合转换条件未满足")

    def _notify_players_of_next_turn(self):
        """通知所有玩家进入下一轮"""
        next_turn = self.get_current_turn()
        if next_turn and next_turn.turn_type == TurnType.PLAYER:
            # 发送消息给所有玩家，告知他们新的玩家回合开始
            for player in self.current_room.players:
                self.reply_to_player(player.id, "新的玩家回合已开始，请提交你的行动")

    def reply_to_player(self, player_id: str, message: str):
        """发送消息给指定玩家"""
        # 实现具体的发送逻辑（例如通过钉钉API）
        logger.info(f"回复玩家 {player_id}: {message}")

    def get_current_turn(self) -> Optional[Turn]:
        """获取当前回合"""
        if self.current_room and self.current_room.current_match:
            return self.current_room.current_match.current_turn
        return None

# 新增异常类
class PlayerTimeoutError(Exception):
    """玩家操作超时异常"""

class InvalidGameOperation(Exception):
    """非法游戏操作异常"""
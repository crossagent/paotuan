from pydantic import BaseModel
from typing import List, Dict, Optional
from enum import Enum  # 导入Enum类
import logging

# 新增自定义异常类
class InvalidTurnOperation(Exception):
    """非法回合操作异常"""

logger = logging.getLogger(__name__)

class Player(BaseModel):
    name: str
    health: int = 100
    alive: bool = True

class StoryNode(BaseModel):
    id: str
    dm_prompt: str
    player_actions: Dict[str, str]

class TurnType(str, Enum):
    DM = "DM"
    PLAYER = "PLAYER"

class TurnStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"

class Turn(BaseModel):
    turn_id: int
    turn_type: TurnType
    actions: Dict[str, str] = {}
    status: TurnStatus = TurnStatus.PENDING
    active_players: List[str] = []

    def process_player_action(self, player_id: str, action: str):
        """处理玩家行动（仅限玩家回合）"""
        if self.turn_type != TurnType.PLAYER:
            raise InvalidTurnOperation("非玩家回合不能处理玩家行动")
        self.actions[player_id] = action
        if self.all_players_submitted():
            self.status = TurnStatus.COMPLETED

    def process_dm_turn(self, narration: str):
        """处理DM叙事（仅限DM回合）"""
        if self.turn_type != TurnType.DM:
            raise InvalidTurnOperation("非DM回合不能处理叙事")
        self.actions["dm_narration"] = narration
        self.status = TurnStatus.COMPLETED

    def all_players_submitted(self) -> bool:
        """检查所有玩家提交（仅限玩家回合）"""
        return self.turn_type == TurnType.PLAYER and \
               set(self.actions.keys()) == set(self.active_players)

    def is_completed(self) -> bool:
        result = self.status == TurnStatus.COMPLETED
        logger.debug(f"回合状态检查：{self.turn_id} {self.status}")
        return result

class Match(BaseModel):
    match_id: int
    scene: str
    turns: List[Turn] = []
    current_turn: Optional[Turn] = None

    def start_new_turn(self, turn_type: TurnType):
        new_turn = Turn(turn_id=len(self.turns) + 1, turn_type=turn_type)
        self.turns.append(new_turn)
        self.current_turn = new_turn
        logger.debug(f"开始新回合，类型：{turn_type} 回合ID：{new_turn.turn_id}")

    def end_current_turn(self):
        if self.current_turn and self.current_turn.is_completed():
            self.current_turn = None
            logger.info(f"结束当前回合，回合ID：{len(self.turns)}")

    def handle_turn_transition(self):
        """处理回合状态转换"""
        if self.current_turn and self.current_turn.is_completed():
            if self.current_turn.turn_type == TurnType.PLAYER:
                # 玩家回合结束→创建DM回合
                self.start_new_turn(TurnType.DM)
                return True
            elif self.current_turn.turn_type == TurnType.DM:
                # DM回合结束→创建玩家回合（需外部设置激活玩家）
                self.start_new_turn(TurnType.PLAYER)
                return True
        return False

class Room(BaseModel):
    room_id: str
    players: List[Player] = []
    current_match: Optional[Match] = None
    history: List[Match] = []

    def create_new_match(self, scene: str):
        new_match = Match(match_id=len(self.history) + 1, scene=scene)
        self.history.append(new_match)
        self.current_match = new_match
        logger.info(f"开始新游戏局，场景：{scene} 房间ID：{self.room_id}")

    def add_player(self, player: Player):
        self.players.append(player)
        if self.current_match and self.current_match.current_turn:
            self.current_match.current_turn.active_players.append(player.name)
            logger.debug(f"玩家{player.name}加入房间，当前回合ID：{self.current_match.current_turn.turn_id}")

# 删除GameLogic类定义

# 示例使用
if __name__ == "__main__":
    room = Room(room_id="room_1")
    room.create_new_match("初始场景")
    player1 = Player(name="Alice")
    room.add_player(player1)
    print("当前房间状态:", room)

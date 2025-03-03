from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from enum import Enum
import logging

# 自定义异常类
class InvalidTurnOperation(Exception):
    """非法回合操作异常"""

logger = logging.getLogger(__name__)

class Player(BaseModel):
    name: str
    id: str
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
    next_turn_info: Dict[str, Any] = {}  # 存储下一个回合的信息，如类型、激活玩家等

    def is_completed(self) -> bool:
        """检查回合是否已完成"""
        return self.status == TurnStatus.COMPLETED

class Match(BaseModel):
    match_id: int
    scene: str
    turns: List[Turn] = []
    current_turn: Optional[Turn] = None

class Room(BaseModel):
    room_id: str
    players: List[Player] = []
    current_match: Optional[Match] = None
    history: List[Match] = []

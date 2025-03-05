from enum import Enum, auto
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime

class GameStatus(str, Enum):
    """游戏状态枚举"""
    WAITING = "WAITING"  # 等待玩家加入
    RUNNING = "RUNNING"  # 游戏进行中
    PAUSED = "PAUSED"    # 游戏暂停
    FINISHED = "FINISHED"  # 游戏结束

class TurnType(str, Enum):
    """回合类型枚举"""
    DM = "DM"  # DM回合
    PLAYER = "PLAYER"  # 玩家回合

class TurnStatus(str, Enum):
    """回合状态枚举"""
    PENDING = "PENDING"  # 等待完成
    COMPLETED = "COMPLETED"  # 已完成

class Player(BaseModel):
    """玩家模型"""
    id: str
    name: str
    joined_at: datetime = datetime.now()
    health: int = 100
    alive: bool = True
    attributes: Dict[str, Any] = {}
    items: List[str] = []

class Turn(BaseModel):
    """回合模型"""
    id: str
    turn_type: TurnType
    status: TurnStatus = TurnStatus.PENDING
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    active_players: List[str] = []
    actions: Dict[str, str] = {}
    next_turn_info: Dict[str, Any] = {}

class Match(BaseModel):
    """游戏局模型"""
    id: str
    status: GameStatus = GameStatus.WAITING
    scene: str
    created_at: datetime = datetime.now()
    turns: List[Turn] = []
    current_turn_id: Optional[str] = None
    game_state: Dict[str, Any] = {}

class Room(BaseModel):
    """房间模型"""
    id: str
    name: str
    created_at: datetime = datetime.now()
    players: List[Player] = []
    matches: List[Match] = []
    current_match_id: Optional[str] = None
    settings: Dict[str, Any] = {}

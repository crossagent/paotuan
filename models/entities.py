from enum import Enum, auto
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Literal
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

class NextTurnInfo(BaseModel):
    """下一回合信息模型"""
    turn_type: TurnType  # 下一回合类型（DM或PLAYER）
    active_players: List[str] = []  # 下一回合激活的玩家ID列表（仅在turn_type为PLAYER时有意义）

class Turn(BaseModel):
    """回合模型"""
    id: str
    turn_type: TurnType
    status: TurnStatus = TurnStatus.PENDING
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    active_players: List[str] = []
    actions: Dict[str, str] = {}
    next_turn_info: Optional[NextTurnInfo] = None  # 下一回合信息，包含回合类型和激活玩家
    
    # 回合模式，只在turn_type为PLAYER时有意义
    turn_mode: Optional[Literal["action", "dice"]] = None
    
    # 掷骰子相关字段，只在turn_mode为"dice"时有意义
    difficulty: Optional[int] = None  # 掷骰子难度
    dice_results: Dict[str, Dict[str, Any]] = {}  # 玩家ID -> {roll: 骰子结果, success: 是否成功, difficulty: 难度, action: 玩家行动}

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

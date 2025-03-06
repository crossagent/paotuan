from enum import Enum, auto
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Literal, Union
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
    """玩家模型 - 代表现实世界的用户"""
    id: str
    name: str
    joined_at: datetime = datetime.now()
    is_ready: bool = False  # 玩家是否已准备
    is_host: bool = False   # 是否为房主
    character_id: Optional[str] = None  # 关联的游戏角色ID

class Character(BaseModel):
    """角色模型 - 代表游戏世界中的实体"""
    id: str
    name: str
    player_id: Optional[str] = None  # 控制此角色的玩家ID，可以为None表示NPC
    health: int = 100
    alive: bool = True
    attributes: Dict[str, Any] = {}
    items: List[str] = []
    location: Optional[str] = None  # 角色当前位置，格式为"楼层/房间"

class NextTurnInfo(BaseModel):
    """下一回合信息模型"""
    turn_type: TurnType  # 下一回合类型（DM或PLAYER）
    active_players: List[str] = []  # 下一回合激活的玩家ID列表（仅在turn_type为PLAYER时有意义）

class BaseTurn(BaseModel):
    """基础回合模型"""
    id: str
    turn_type: TurnType
    status: TurnStatus = TurnStatus.PENDING
    created_at: datetime = datetime.now()
    completed_at: Optional[datetime] = None
    next_turn_info: Optional[NextTurnInfo] = None  # 下一回合信息，包含回合类型和激活玩家

class DMTurn(BaseTurn):
    """DM回合模型"""
    narration: str = ""  # DM的叙述内容

class ActionTurn(BaseTurn):
    """玩家行动回合模型"""
    active_players: List[str] = []
    actions: Dict[str, str] = {}  # 玩家ID -> 行动描述

class DiceTurn(BaseTurn):
    """掷骰子回合模型"""
    active_players: List[str] = []
    difficulty: int  # 掷骰子难度
    action_desc: str  # 行动类型描述（如"攀爬"、"说服"等）
    dice_results: Dict[str, Dict[str, Any]] = {}  # 玩家ID -> {roll, success, difficulty, action}

# 为了向后兼容，保留Turn类，但使用Union类型
Turn = Union[BaseTurn, DMTurn, ActionTurn, DiceTurn]

class Match(BaseModel):
    """游戏局模型"""
    id: str
    status: GameStatus = GameStatus.WAITING
    scene: str
    created_at: datetime = datetime.now()
    turns: List[Union[BaseTurn, DMTurn, ActionTurn, DiceTurn]] = []
    current_turn_id: Optional[str] = None
    game_state: Dict[str, Any] = {}
    scenario_id: Optional[str] = None  # 关联的剧本ID
    characters: List[Character] = []  # 游戏局中的角色列表
    available_characters: List[Dict[str, Any]] = []  # 可选角色列表

class Room(BaseModel):
    """房间模型"""
    id: str
    name: str
    created_at: datetime = datetime.now()
    players: List[Player] = []
    matches: List[Match] = []
    current_match_id: Optional[str] = None
    settings: Dict[str, Any] = {}
    host_id: Optional[str] = None  # 房主ID

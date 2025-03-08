from typing import Dict, List, Optional, Any, Literal, Union, Tuple
import uuid
import logging
from datetime import datetime

from models.entities import BaseTurn, DMTurn, ActionTurn, DiceTurn, TurnType, TurnStatus, NextTurnInfo

logger = logging.getLogger(__name__)

class TurnContext:
    """回合上下文，提供Turn实体的上下文环境"""
    
    def __init__(self, turn: Union[DMTurn, ActionTurn, DiceTurn]):
        """初始化回合上下文
        
        Args:
            turn: Union[DMTurn, ActionTurn, DiceTurn] - 回合实体
        """
        self.turn = turn
        
    def dump_state(self) -> Dict[str, Any]:
        """返回当前状态供Inspector使用
        
        Returns:
            Dict[str, Any]: 回合状态
        """
        turn_info = {
            "id": self.turn.id,
            "turn_type": self.turn.turn_type,
            "status": self.turn.status,
            "created_at": self.turn.created_at.isoformat() if self.turn.created_at else None,
            "completed_at": self.turn.completed_at.isoformat() if self.turn.completed_at else None
        }
        
        # 添加回合类型特有的信息
        if isinstance(self.turn, DMTurn):
            turn_info["narration"] = self.turn.narration
            
        elif isinstance(self.turn, ActionTurn):
            turn_info["active_players"] = self.turn.active_players
            turn_info["actions"] = self.turn.actions
            
        elif isinstance(self.turn, DiceTurn):
            turn_info["active_players"] = self.turn.active_players
            turn_info["difficulty"] = self.turn.difficulty
            turn_info["action_desc"] = self.turn.action_desc
            turn_info["dice_results"] = self.turn.dice_results
            
        return turn_info
    
    @classmethod
    def create_dm_turn(cls) -> "TurnContext":
        """创建新的DM回合
        
        Returns:
            TurnContext - 新创建的回合上下文
        """
        turn_id = str(uuid.uuid4())
        new_turn = DMTurn(
            id=turn_id,
            turn_type=TurnType.DM,
            created_at=datetime.now()
        )
        
        logger.info(f"创建新DM回合: ID={turn_id}")
        
        return cls(new_turn)
    
    @classmethod
    def create_action_turn(cls, active_players: List[str]) -> "TurnContext":
        """创建新的玩家行动回合
        
        Args:
            active_players: List[str] - 激活的玩家ID列表
            
        Returns:
            TurnContext - 新创建的回合上下文
        """
        turn_id = str(uuid.uuid4())
        new_turn = ActionTurn(
            id=turn_id,
            turn_type=TurnType.PLAYER,
            active_players=active_players,
            created_at=datetime.now()
        )
        
        logger.info(f"创建新玩家行动回合: ID={turn_id}, 激活玩家数={len(active_players)}")
        
        return cls(new_turn)
    
    @classmethod
    def create_dice_turn(cls, active_players: List[str], difficulty: int, action_desc: str = "行动") -> "TurnContext":
        """创建新的掷骰子回合
        
        Args:
            active_players: List[str] - 激活的玩家ID列表
            difficulty: int - 难度
            action_desc: str - 行动描述
            
        Returns:
            TurnContext - 新创建的回合上下文
        """
        turn_id = str(uuid.uuid4())
        new_turn = DiceTurn(
            id=turn_id,
            turn_type=TurnType.PLAYER,
            active_players=active_players,
            difficulty=difficulty,
            action_desc=action_desc,
            created_at=datetime.now()
        )
        
        logger.info(f"创建新掷骰子回合: ID={turn_id}, 难度={difficulty}, 行动描述={action_desc}, 激活玩家数={len(active_players)}")
        
        return cls(new_turn)
    
    def complete_turn(self, next_turn_type: Optional[TurnType] = None, next_active_players: Optional[List[str]] = None) -> None:
        """完成当前回合
        
        Args:
            next_turn_type: Optional[TurnType] - 下一回合类型
            next_active_players: Optional[List[str]] - 下一回合激活的玩家ID列表
        """
        self.turn.status = TurnStatus.COMPLETED
        self.turn.completed_at = datetime.now()
        
        # 设置下一回合信息
        if next_turn_type:
            # 根据下一回合类型决定激活玩家
            active_players = []
            if next_turn_type == TurnType.PLAYER:
                active_players = next_active_players or []
            
            # 设置NextTurnInfo对象
            self.turn.next_turn_info = NextTurnInfo(
                turn_type=next_turn_type,
                active_players=active_players
            )
            
        logger.info(f"完成回合: {self.turn.id}")
    
    def set_narration(self, narration: str) -> None:
        """设置DM回合的叙述内容
        
        Args:
            narration: str - 叙述内容
        """
        if isinstance(self.turn, DMTurn):
            self.turn.narration = narration
            logger.info(f"设置DM回合 {self.turn.id} 的叙述内容")
        else:
            logger.warning(f"无法设置叙述内容: 当前回合不是DM回合")
    
    def record_player_action(self, player_id: str, action: str) -> bool:
        """记录玩家行动
        
        Args:
            player_id: str - 玩家ID
            action: str - 行动描述
            
        Returns:
            bool - 是否成功记录
        """
        # 检查回合类型
        if not isinstance(self.turn, ActionTurn):
            logger.warning(f"无法记录玩家行动: 当前回合不是行动回合")
            return False
            
        # 检查玩家是否在激活列表中
        if player_id not in self.turn.active_players:
            logger.warning(f"无法记录玩家行动: 玩家 {player_id} 不在激活列表中")
            return False
            
        # 检查玩家是否已经行动过
        if player_id in self.turn.actions:
            logger.warning(f"无法记录玩家行动: 玩家 {player_id} 已经行动过")
            return False
            
        # 记录玩家行动
        self.turn.actions[player_id] = action
        logger.info(f"记录玩家行动: 玩家ID={player_id}, 行动={action}")
        
        # 检查是否所有玩家都已行动
        if self.all_players_acted():
            self.turn.status = TurnStatus.COMPLETED
            self.turn.completed_at = datetime.now()
            logger.info(f"所有玩家已行动，回合 {self.turn.id} 完成")
            
        return True
    
    def record_dice_result(self, player_id: str, roll: int, success: bool, action: str) -> bool:
        """记录掷骰子结果
        
        Args:
            player_id: str - 玩家ID
            roll: int - 骰子点数
            success: bool - 是否成功
            action: str - 行动描述
            
        Returns:
            bool - 是否成功记录
        """
        # 检查回合类型
        if not isinstance(self.turn, DiceTurn):
            logger.warning(f"无法记录掷骰子结果: 当前回合不是掷骰子回合")
            return False
            
        # 检查玩家是否在激活列表中
        if player_id not in self.turn.active_players:
            logger.warning(f"无法记录掷骰子结果: 玩家 {player_id} 不在激活列表中")
            return False
            
        # 检查玩家是否已经掷过骰子
        if player_id in self.turn.dice_results:
            logger.warning(f"无法记录掷骰子结果: 玩家 {player_id} 已经掷过骰子")
            return False
            
        # 记录掷骰子结果
        self.turn.dice_results[player_id] = {
            "roll": roll,
            "success": success,
            "difficulty": self.turn.difficulty,
            "action": action
        }
        
        logger.info(f"记录掷骰子结果: 玩家ID={player_id}, 点数={roll}, 难度={self.turn.difficulty}, 结果={'成功' if success else '失败'}")
        
        # 检查是否所有玩家都已掷骰子
        if self.all_players_acted():
            self.turn.status = TurnStatus.COMPLETED
            self.turn.completed_at = datetime.now()
            logger.info(f"所有玩家已掷骰子，回合 {self.turn.id} 完成")
            
        return True
    
    def all_players_acted(self) -> bool:
        """检查所有激活玩家是否都已行动
        
        Returns:
            bool - 是否所有激活玩家都已行动
        """
        if isinstance(self.turn, ActionTurn):
            return set(self.turn.actions.keys()) == set(self.turn.active_players)
        elif isinstance(self.turn, DiceTurn):
            return set(self.turn.dice_results.keys()) == set(self.turn.active_players)
        else:
            return True  # 对于DM回合，总是返回True
    
    def get_active_players(self) -> List[str]:
        """获取激活玩家列表
        
        Returns:
            List[str] - 激活玩家ID列表
        """
        if isinstance(self.turn, (ActionTurn, DiceTurn)):
            return self.turn.active_players
        return []
    
    def get_player_action(self, player_id: str) -> Optional[str]:
        """获取玩家行动
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[str] - 玩家行动，如果不存在则返回None
        """
        if isinstance(self.turn, ActionTurn) and player_id in self.turn.actions:
            return self.turn.actions[player_id]
        return None
    
    def get_player_dice_result(self, player_id: str) -> Optional[Dict[str, Any]]:
        """获取玩家掷骰子结果
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[Dict[str, Any]] - 玩家掷骰子结果，如果不存在则返回None
        """
        if isinstance(self.turn, DiceTurn) and player_id in self.turn.dice_results:
            return self.turn.dice_results[player_id]
        return None
    
    def get_narration(self) -> Optional[str]:
        """获取DM回合的叙述内容
        
        Returns:
            Optional[str] - 叙述内容，如果不存在则返回None
        """
        if isinstance(self.turn, DMTurn):
            return self.turn.narration
        return None

from typing import Dict, List, Optional, Any, Literal
import uuid
import logging
from datetime import datetime

from models.entities import Match, Turn, TurnType, TurnStatus, Player, NextTurnInfo
from core.rules import RuleEngine
from adapters.base import GameEvent, PlayerActionEvent, DMNarrationEvent

logger = logging.getLogger(__name__)

class TurnManager:
    """回合管理器"""
    
    def __init__(self, match: Match):
        self.match = match
        
    def start_new_turn(self, turn_type: TurnType, active_players: List[str] = None, 
                      turn_mode: Optional[Literal["action", "dice"]] = None,
                      difficulty: Optional[int] = None) -> Turn:
        """开始新回合"""
        turn_id = str(uuid.uuid4())
        
        # 初始化新回合
        new_turn = Turn(
            id=turn_id,
            turn_type=turn_type,
            active_players=active_players or []
        )
        
        # 如果是玩家回合，设置回合模式
        if turn_type == TurnType.PLAYER and turn_mode:
            new_turn.turn_mode = turn_mode
            
            # 如果是掷骰子回合，设置难度
            if turn_mode == "dice" and difficulty is not None:
                new_turn.difficulty = difficulty
        
        self.match.turns.append(new_turn)
        self.match.current_turn_id = turn_id
        
        logger.info(f"开始新回合: {turn_type} (模式: {turn_mode or 'N/A'}, ID: {turn_id})")
        return new_turn
    
    def get_current_turn(self) -> Optional[Turn]:
        """获取当前回合"""
        if not self.match.current_turn_id:
            return None
            
        for turn in self.match.turns:
            if turn.id == self.match.current_turn_id:
                return turn
                
        return None
    
    def complete_current_turn(self, next_turn_type: TurnType = None, next_active_players: List[str] = None) -> None:
        """完成当前回合"""
        current_turn = self.get_current_turn()
        if not current_turn:
            logger.warning("没有当前回合，无法完成")
            return
            
        # 完成当前回合
        current_turn.status = TurnStatus.COMPLETED
        current_turn.completed_at = datetime.now()
        
        # 设置下一回合信息
        if next_turn_type:
            # 根据下一回合类型决定激活玩家
            active_players = []
            if next_turn_type == TurnType.PLAYER:
                active_players = next_active_players or []
            
            # 设置NextTurnInfo对象
            current_turn.next_turn_info = NextTurnInfo(
                turn_type=next_turn_type,
                active_players=active_players
            )
            
        logger.info(f"完成回合: {current_turn.id}")
    
    def handle_player_action(self, player_id: str, action: str) -> bool:
        """处理玩家行动"""
        current_turn = self.get_current_turn()
        if not current_turn:
            logger.warning("没有当前回合，无法处理玩家行动")
            return False
            
        # 检查是否是玩家回合
        if current_turn.turn_type != TurnType.PLAYER:
            logger.warning(f"当前不是玩家回合 (当前: {current_turn.turn_type})")
            return False
            
        # 检查玩家是否在激活列表中
        if player_id not in current_turn.active_players:
            logger.warning(f"玩家不在激活列表中: {player_id}")
            return False
        
        # 根据回合模式处理玩家行动
        if current_turn.turn_mode == "action" or current_turn.turn_mode is None:
            # 普通行动回合：记录玩家行动
            current_turn.actions[player_id] = action
            logger.info(f"记录玩家行动: {player_id}, {action}")
        
        elif current_turn.turn_mode == "dice":
            # 掷骰子回合：不记录action，直接进行掷骰子
            difficulty = current_turn.difficulty or 10  # 默认难度为10
            
            # 使用规则引擎处理掷骰子
            rule_engine = RuleEngine()
            success, roll = rule_engine.handle_dice_check(action, difficulty)
            
            # 记录掷骰子结果，但不记录"掷骰子"这个action
            current_turn.dice_results[player_id] = {
                "roll": roll,
                "success": success,
                "difficulty": difficulty,
                "action": action  # 记录玩家实际想做的行动
            }
            
            logger.info(f"玩家 {player_id} 尝试: {action}, 掷骰子结果: {roll}, 难度: {difficulty}, {'成功' if success else '失败'}")
        
        # 检查是否所有玩家都已行动
        if self.all_players_acted():
            current_turn.status = TurnStatus.COMPLETED
            current_turn.completed_at = datetime.now()
            logger.info("所有玩家已行动，回合完成")
            
        return True
    
    def all_players_acted(self) -> bool:
        """检查所有激活玩家是否都已行动"""
        current_turn = self.get_current_turn()
        if not current_turn:
            return False
        
        if current_turn.turn_mode == "dice":
            # 掷骰子回合：检查所有玩家是否都有掷骰子结果
            return set(current_turn.dice_results.keys()) == set(current_turn.active_players)
        else:
            # 其他回合类型：检查actions
            return set(current_turn.actions.keys()) == set(current_turn.active_players)

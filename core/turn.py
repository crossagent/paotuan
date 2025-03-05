from typing import Dict, List, Optional, Any
import uuid
import logging
from datetime import datetime

from models.entities import Match, Turn, TurnType, TurnStatus, Player
from adapters.base import GameEvent, PlayerActionEvent, DMNarrationEvent

logger = logging.getLogger(__name__)

class TurnManager:
    """回合管理器"""
    
    def __init__(self, match: Match):
        self.match = match
        
    def start_new_turn(self, turn_type: TurnType, active_players: List[str] = None) -> Turn:
        """开始新回合"""
        turn_id = str(uuid.uuid4())
        new_turn = Turn(
            id=turn_id,
            turn_type=turn_type,
            active_players=active_players or []
        )
        
        self.match.turns.append(new_turn)
        self.match.current_turn_id = turn_id
        
        logger.info(f"开始新回合: {turn_type} (ID: {turn_id})")
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
            current_turn.next_turn_info = {
                "turn_type": next_turn_type,
                "active_players": next_active_players or []
            }
            
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
            
        # 记录玩家行动
        current_turn.actions[player_id] = action
        logger.info(f"记录玩家行动: {player_id}, {action}")
        
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
            
        return set(current_turn.actions.keys()) == set(current_turn.active_players)

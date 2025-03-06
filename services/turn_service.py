import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import TurnType, DMTurn

logger = logging.getLogger(__name__)

class TurnService:
    """回合服务，处理回合转换相关的业务逻辑"""
    
    def __init__(self, rule_engine):
        self.rule_engine = rule_engine
        
    async def handle_turn_transition(self, response, current_turn, turn_manager, player_ids) -> List[Dict[str, str]]:
        """处理回合转换和通知玩家"""
        messages = []
        narration = response.narration
        
        # 保存DM叙述到DMTurn对象
        if isinstance(current_turn, DMTurn):
            current_turn.narration = narration
        
        # 完成DM回合，准备下一个玩家回合
        turn_manager.complete_current_turn(TurnType.PLAYER, response.active_players)
        
        # 根据是否需要骰子检定创建不同类型的回合
        if response.need_dice_roll and response.difficulty:
            # 创建新的掷骰子回合
            action_desc = response.action_desc or "行动"
            turn_manager.start_new_turn(
                TurnType.PLAYER, 
                response.active_players,
                turn_mode="dice",
                difficulty=response.difficulty,
                action_desc=action_desc
            )
            
            # 通知所有玩家
            for player_id in player_ids:
                messages.append({"recipient": player_id, "content": narration})
            
            # 通知激活玩家
            for player_id in response.active_players:
                messages.append({
                    "recipient": player_id, 
                    "content": f"需要进行 {action_desc} 的骰子检定，难度为 {response.difficulty}。请描述你的具体行动。"
                })
        else:
            # 创建新的普通玩家回合
            turn_manager.start_new_turn(
                TurnType.PLAYER, 
                response.active_players,
                turn_mode="action"
            )
            
            # 通知所有玩家
            for player_id in player_ids:
                messages.append({"recipient": player_id, "content": narration})
            
            # 通知激活玩家
            for player_id in response.active_players:
                messages.append({
                    "recipient": player_id, 
                    "content": "轮到你行动了，请输入你的行动。"
                })
                
        return messages

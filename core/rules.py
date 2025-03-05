from typing import Dict, List, Optional, Any, Tuple, Union
import random
import logging

from models.entities import Player, Match, Turn, TurnType, DiceTurn

logger = logging.getLogger(__name__)

class RuleEngine:
    """游戏规则引擎"""
    
    def roll_dice(self, sides: int = 20) -> int:
        """掷骰子"""
        return random.randint(1, sides)
    
    def check_success(self, roll: int, difficulty: int) -> bool:
        """检查是否成功"""
        return roll >= difficulty
    
    def handle_dice_check(self, action: str, difficulty: int) -> Tuple[bool, int]:
        """处理骰子检定"""
        roll = self.roll_dice()
        success = self.check_success(roll, difficulty)
        return success, roll
    
    def apply_health_change(self, player: Player, change: int) -> None:
        """应用生命值变化"""
        player.health += change
        # 确保生命值在有效范围内
        player.health = max(0, min(100, player.health))
        # 更新存活状态
        player.alive = player.health > 0
        
    def process_dice_turn_results(self, turn: DiceTurn) -> Dict[str, Any]:
        """处理掷骰子回合的结果，返回处理后的综合结果
        
        注意：每个玩家投出的骰子只对自己生效，这里只是为了显示而汇总结果
        """
        # 汇总所有玩家的掷骰子结果，添加行动描述
        results = {
            "summary": [],
            "action_desc": turn.action_desc  # 添加行动描述
        }
        
        for player_id, dice_result in turn.dice_results.items():
            player_result = {
                "player_id": player_id,
                "action": dice_result.get("action", ""),  # 玩家实际想做的行动
                "roll": dice_result["roll"],
                "success": dice_result["success"],
                "difficulty": dice_result["difficulty"]
            }
            results["summary"].append(player_result)
        
        return results

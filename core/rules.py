from typing import Dict, List, Optional, Any, Tuple
import random
import logging

from models.entities import Player, Match, Turn

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

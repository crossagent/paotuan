from typing import Dict, List, Optional, Any, Literal, Union, cast
import uuid
import logging
from datetime import datetime

from models.entities import Match, BaseTurn, DMTurn, ActionTurn, DiceTurn, TurnType, TurnStatus, Player, Character, NextTurnInfo
from core.rules import RuleEngine
from adapters.base import GameEvent, PlayerActionEvent, DMNarrationEvent

logger = logging.getLogger(__name__)

class TurnController:
    """回合控制器"""
    
    def __init__(self, match: Match):
        self.match = match
        
    def dump_state(self) -> Dict[str, Any]:
        """返回当前状态供Inspector使用
        
        Returns:
            Dict[str, Any]: 回合状态
        """
        current_turn = self.get_current_turn()
        current_turn_info = None
        
        if current_turn:
            current_turn_info = {
                "id": current_turn.id,
                "turn_type": current_turn.turn_type,
                "status": current_turn.status,
                "created_at": current_turn.created_at.isoformat() if current_turn.created_at else None,
                "completed_at": current_turn.completed_at.isoformat() if current_turn.completed_at else None
            }
            
            # 添加回合类型特有的信息
            if isinstance(current_turn, DMTurn):
                current_turn_info["narration"] = current_turn.narration
                
            elif isinstance(current_turn, ActionTurn):
                current_turn_info["active_players"] = current_turn.active_players
                current_turn_info["actions"] = current_turn.actions
                
            elif isinstance(current_turn, DiceTurn):
                current_turn_info["active_players"] = current_turn.active_players
                current_turn_info["difficulty"] = current_turn.difficulty
                current_turn_info["action_desc"] = current_turn.action_desc
                current_turn_info["dice_results"] = current_turn.dice_results
        
        turns = []
        for turn in self.match.turns:
            turn_info = {
                "id": turn.id,
                "turn_type": turn.turn_type,
                "status": turn.status,
                "created_at": turn.created_at.isoformat() if turn.created_at else None,
                "completed_at": turn.completed_at.isoformat() if turn.completed_at else None
            }
            
            # 添加回合类型特有的信息
            if isinstance(turn, DMTurn):
                turn_info["narration"] = turn.narration
                
            elif isinstance(turn, ActionTurn):
                turn_info["active_players"] = turn.active_players
                turn_info["actions"] = turn.actions
                
            elif isinstance(turn, DiceTurn):
                turn_info["active_players"] = turn.active_players
                turn_info["difficulty"] = turn.difficulty
                turn_info["action_desc"] = turn.action_desc
                turn_info["dice_results"] = turn.dice_results
                
            turns.append(turn_info)
            
        return {
            "match_id": self.match.id,
            "current_turn": current_turn_info,
            "turns": turns,
            "turn_count": len(self.match.turns)
        }
        
    def start_new_turn(self, turn_type: TurnType, active_players: List[str] = None, 
                      turn_mode: Optional[Literal["action", "dice"]] = None,
                      difficulty: Optional[int] = None,
                      action_desc: Optional[str] = None) -> Union[DMTurn, ActionTurn, DiceTurn]:
        """开始新回合"""
        turn_id = str(uuid.uuid4())
        
        # 根据回合类型创建相应的回合对象
        if turn_type == TurnType.DM:
            new_turn = DMTurn(
                id=turn_id,
                turn_type=turn_type
            )
            logger.info(f"开始新DM回合: ID: {turn_id}")
        elif turn_type == TurnType.PLAYER:
            if turn_mode == "dice":
                if difficulty is None:
                    raise ValueError("掷骰子回合必须指定难度")
                new_turn = DiceTurn(
                    id=turn_id,
                    turn_type=turn_type,
                    active_players=active_players or [],
                    difficulty=difficulty,
                    action_desc=action_desc or "行动"
                )
                logger.info(f"开始新掷骰子回合: 难度: {difficulty}, 行动描述: {action_desc or '行动'}, ID: {turn_id}")
            else:  # 普通行动回合
                new_turn = ActionTurn(
                    id=turn_id,
                    turn_type=turn_type,
                    active_players=active_players or []
                )
                logger.info(f"开始新行动回合: ID: {turn_id}")
        else:
            raise ValueError(f"不支持的回合类型: {turn_type}")
        
        self.match.turns.append(new_turn)
        self.match.current_turn_id = turn_id
        
        return new_turn
    
    def get_current_turn(self) -> Optional[Union[DMTurn, ActionTurn, DiceTurn]]:
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
        if not hasattr(current_turn, 'active_players') or player_id not in current_turn.active_players:
            logger.warning(f"玩家不在激活列表中: {player_id}")
            return False
        
        # 根据回合类型处理玩家行动
        if isinstance(current_turn, ActionTurn):
            # 普通行动回合：记录玩家行动
            current_turn.actions[player_id] = action
            logger.info(f"记录玩家行动: {player_id}, {action}")
        
        elif isinstance(current_turn, DiceTurn):
            # 掷骰子回合：不记录action，直接进行掷骰子
            difficulty = current_turn.difficulty  # 从DiceTurn获取难度
            
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
            
            # 如果判定失败，减少角色血量
            if not success:
                # 获取玩家对应的角色
                character = None
                # 从房间中查找角色
                for room in self.match.game_instance.rooms.values():
                    for player in room.players:
                        if player.id == player_id:
                            # 找到玩家后，查找对应的角色
                            for char in room.characters:
                                if char.player_id == player_id:
                                    character = char
                                    break
                            break
                    if character:
                        break
                
                if character:
                    # 使用规则引擎计算失败伤害并应用
                    health_change = rule_engine.calculate_failure_damage(difficulty)
                    rule_engine.apply_health_change(character, health_change)
                    logger.info(f"角色 {character.id} (玩家 {player_id}) 判定失败，生命值变化: {health_change}，当前生命值: {character.health}")
            
            logger.info(f"玩家 {player_id} 尝试: {action}, 掷骰子结果: {roll}, 难度: {difficulty}, {'成功' if success else '失败'}")
        else:
            logger.warning(f"不支持的玩家回合类型: {type(current_turn)}")
            return False
        
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
        
        if not hasattr(current_turn, 'active_players'):
            return True  # 如果没有激活玩家列表，认为已完成
        
        if isinstance(current_turn, DiceTurn):
            # 掷骰子回合：检查所有玩家是否都有掷骰子结果
            return set(current_turn.dice_results.keys()) == set(current_turn.active_players)
        elif isinstance(current_turn, ActionTurn):
            # 行动回合：检查actions
            return set(current_turn.actions.keys()) == set(current_turn.active_players)
        else:
            return True  # 其他类型回合默认完成

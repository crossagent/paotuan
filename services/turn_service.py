import logging
from typing import List, Dict, Any, Optional, Union, Tuple

from models.entities import TurnType, DMTurn, ActionTurn, DiceTurn, TurnStatus, GameStatus, Match, Character, BaseTurn
from core.turn import TurnManager
from core.rules import RuleEngine
from ai.chains.story_gen import StoryResponse

logger = logging.getLogger(__name__)

class TurnService:
    """回合服务，处理回合转换相关的业务逻辑"""
    
    def __init__(self, rule_engine: RuleEngine = None, event_bus = None):
        """初始化回合服务
        
        Args:
            rule_engine: 规则引擎
            event_bus: 事件总线，用于发布事件和消息
        """
        self.rule_engine = rule_engine or RuleEngine()
        self.event_bus = event_bus
    
    def can_start_turn(self, turn_type: TurnType, match: Match, active_players: List[str] = None) -> Tuple[bool, str]:
        """验证是否可以开始某类回合
        
        Args:
            turn_type: 回合类型
            match: 游戏局
            active_players: 激活的玩家列表（仅对玩家回合有效）
            
        Returns:
            Tuple[bool, str]: (是否可以开始, 原因)
        """
        # 检查游戏状态
        if match.status != GameStatus.RUNNING:
            return False, f"游戏未在运行中，当前状态: {match.status}"
        
        # 获取当前回合
        current_turn = None
        if match.current_turn_id:
            for turn in match.turns:
                if turn.id == match.current_turn_id:
                    current_turn = turn
                    break
        
        # 检查当前回合状态
        if current_turn and current_turn.status != TurnStatus.COMPLETED:
            return False, f"当前回合未完成，无法开始新回合"
        
        # 对于玩家回合，检查是否有激活玩家
        if turn_type == TurnType.PLAYER and (not active_players or len(active_players) == 0):
            return False, "玩家回合必须指定激活玩家"
            
        return True, "可以开始回合"
    
    def can_player_act(self, player_id: str, turn: Union[ActionTurn, DiceTurn]) -> Tuple[bool, str]:
        """验证玩家是否可以在当前回合行动
        
        Args:
            player_id: 玩家ID
            turn: 当前回合
            
        Returns:
            Tuple[bool, str]: (是否可以行动, 原因)
        """
        # 检查回合类型
        if not isinstance(turn, (ActionTurn, DiceTurn)):
            return False, "当前不是玩家行动回合"
        
        # 检查回合状态
        if turn.status != TurnStatus.PENDING:
            return False, f"当前回合状态不允许行动: {turn.status}"
        
        # 检查玩家是否在激活列表中
        if player_id not in turn.active_players:
            return False, "你不在当前回合的激活玩家列表中"
        
        # 检查玩家是否已经行动过
        if isinstance(turn, ActionTurn) and player_id in turn.actions:
            return False, "你已经在当前回合行动过了"
        
        if isinstance(turn, DiceTurn) and player_id in turn.dice_results:
            return False, "你已经在当前回合进行过骰子检定了"
            
        return True, "可以行动"
    
    async def transition_to_dm_turn(self, match: Match, turn_manager: TurnManager) -> Tuple[DMTurn, List[Dict[str, str]]]:
        """转换到DM回合
        
        Args:
            match: 游戏局
            turn_manager: 回合管理器
            
        Returns:
            Tuple[DMTurn, List[Dict[str, str]]]: (新的DM回合, 通知消息列表)
        """
        messages = []
        
        # 完成当前回合（如果有）
        current_turn = turn_manager.get_current_turn()
        if current_turn and current_turn.status != TurnStatus.COMPLETED:
            turn_manager.complete_current_turn(TurnType.DM)
        
        # 创建新的DM回合
        dm_turn = turn_manager.start_new_turn(TurnType.DM)
        logger.info(f"创建新的DM回合: ID={dm_turn.id}")
        
        return dm_turn, messages
    
    async def transition_to_player_turn(self, match: Match, turn_manager: TurnManager, 
                                       active_players: List[str], turn_mode: str = "action",
                                       difficulty: Optional[int] = None, 
                                       action_desc: Optional[str] = None) -> Tuple[Union[ActionTurn, DiceTurn], List[Dict[str, str]]]:
        """转换到玩家回合
        
        Args:
            match: 游戏局
            turn_manager: 回合管理器
            active_players: 激活的玩家列表
            turn_mode: 回合模式，"action"或"dice"
            difficulty: 骰子检定难度（仅在turn_mode为"dice"时有效）
            action_desc: 行动描述（仅在turn_mode为"dice"时有效）
            
        Returns:
            Tuple[Union[ActionTurn, DiceTurn], List[Dict[str, str]]]: (新的玩家回合, 通知消息列表)
        """
        messages = []
        
        # 完成当前回合（如果有）
        current_turn = turn_manager.get_current_turn()
        if current_turn and current_turn.status != TurnStatus.COMPLETED:
            turn_manager.complete_current_turn(TurnType.PLAYER, active_players)
        
        # 创建新的玩家回合
        if turn_mode == "dice":
            if not difficulty:
                raise ValueError("掷骰子回合必须指定难度")
                
            new_turn = turn_manager.start_new_turn(
                TurnType.PLAYER,
                active_players,
                turn_mode="dice",
                difficulty=difficulty,
                action_desc=action_desc or "行动"
            )
            
            logger.info(f"创建新的掷骰子回合: ID={new_turn.id}, 难度={difficulty}, 行动描述={action_desc or '行动'}")
            
            # 通知激活玩家
            for player_id in active_players:
                messages.append({
                    "recipient": player_id,
                    "content": f"需要进行 {action_desc or '行动'} 的骰子检定，难度为 {difficulty}。请描述你的具体行动。"
                })
        else:
            new_turn = turn_manager.start_new_turn(
                TurnType.PLAYER,
                active_players,
                turn_mode="action"
            )
            
            logger.info(f"创建新的普通玩家回合: ID={new_turn.id}")
            
            # 通知激活玩家
            for player_id in active_players:
                messages.append({
                    "recipient": player_id,
                    "content": "轮到你行动了，请输入你的行动。"
                })
                
        return new_turn, messages
    
    async def process_player_action(self, player_id: str, action: str, turn: Union[ActionTurn, DiceTurn], 
                                   turn_manager: TurnManager, character: Optional[Character] = None) -> Tuple[bool, List[Dict[str, str]]]:
        """处理玩家行动
        
        Args:
            player_id: 玩家ID
            action: 行动描述
            turn: 当前回合
            turn_manager: 回合管理器
            character: 玩家角色（可选）
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功处理, 通知消息列表)
        """
        messages = []
        
        # 验证玩家是否可以行动
        can_act, reason = self.can_player_act(player_id, turn)
        if not can_act:
            messages.append({"recipient": player_id, "content": reason})
            return False, messages
        
        # 处理玩家行动
        success = turn_manager.handle_player_action(player_id, action)
        if not success:
            messages.append({"recipient": player_id, "content": "无法处理你的行动"})
            return False, messages
        
        # 检查回合是否完成
        if turn.status == TurnStatus.COMPLETED:
            # 如果是掷骰子回合，处理掷骰子结果
            if isinstance(turn, DiceTurn):
                dice_results = self.rule_engine.process_dice_turn_results(turn)
                
                # 构建结果消息
                result_message = "【掷骰子结果】\n"
                for result in dice_results.get("summary", []):
                    player_name = result["player_id"]  # 这里应该从玩家列表中获取名称
                    result_message += f"{player_name} 尝试 {result['action']}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
                
                # 添加到消息列表
                messages.append({"recipient": player_id, "content": result_message})
        
        return True, messages
    
    async def process_dice_result(self, dice_turn: DiceTurn) -> Dict[str, Any]:
        """处理骰子结果
        
        Args:
            dice_turn: 骰子回合
            
        Returns:
            Dict[str, Any]: 处理后的结果
        """
        return self.rule_engine.process_dice_turn_results(dice_turn)
    
    async def notify_turn_start(self, turn: BaseTurn, player_ids: List[str]) -> List[Dict[str, str]]:
        """通知回合开始
        
        Args:
            turn: 回合对象
            player_ids: 玩家ID列表
            
        Returns:
            List[Dict[str, str]]: 通知消息列表
        """
        messages = []
        
        if turn.turn_type == TurnType.DM:
            # DM回合开始通知
            for player_id in player_ids:
                messages.append({
                    "recipient": player_id,
                    "content": "DM正在思考中..."
                })
        elif turn.turn_type == TurnType.PLAYER:
            # 玩家回合开始通知
            if isinstance(turn, DiceTurn):
                # 掷骰子回合
                for player_id in player_ids:
                    if player_id in turn.active_players:
                        messages.append({
                            "recipient": player_id,
                            "content": f"需要进行 {turn.action_desc} 的骰子检定，难度为 {turn.difficulty}。请描述你的具体行动。"
                        })
                    else:
                        messages.append({
                            "recipient": player_id,
                            "content": f"等待玩家进行 {turn.action_desc} 的骰子检定，难度为 {turn.difficulty}。"
                        })
            else:
                # 普通行动回合
                for player_id in player_ids:
                    if player_id in turn.active_players:
                        messages.append({
                            "recipient": player_id,
                            "content": "轮到你行动了，请输入你的行动。"
                        })
                    else:
                        messages.append({
                            "recipient": player_id,
                            "content": "等待其他玩家行动..."
                        })
                        
        return messages
    
    async def notify_turn_complete(self, turn: BaseTurn, player_ids: List[str], results: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
        """通知回合结束
        
        Args:
            turn: 回合对象
            player_ids: 玩家ID列表
            results: 回合结果（可选）
            
        Returns:
            List[Dict[str, str]]: 通知消息列表
        """
        messages = []
        
        if turn.turn_type == TurnType.DM:
            # DM回合结束通知
            if isinstance(turn, DMTurn) and turn.narration:
                for player_id in player_ids:
                    messages.append({
                        "recipient": player_id,
                        "content": turn.narration
                    })
        elif turn.turn_type == TurnType.PLAYER:
            # 玩家回合结束通知
            if isinstance(turn, DiceTurn) and results:
                # 掷骰子回合结果通知
                result_message = "【掷骰子结果】\n"
                for result in results.get("summary", []):
                    player_name = result["player_id"]  # 这里应该从玩家列表中获取名称
                    result_message += f"{player_name} 尝试 {result['action']}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
                
                for player_id in player_ids:
                    messages.append({
                        "recipient": player_id,
                        "content": result_message
                    })
                    
        return messages
        
    async def handle_turn_transition(self, response: Union[Dict[str, Any], Any], current_turn: Union[DMTurn, ActionTurn, DiceTurn], turn_manager: TurnManager, player_ids: List[str]) -> List[Dict[str, str]]:
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

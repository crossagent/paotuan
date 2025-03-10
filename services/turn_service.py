import logging
from typing import List, Dict, Any, Optional, Union, Tuple

from models.entities import TurnType, DMTurn, ActionTurn, DiceTurn, SystemTurn, SystemTurnType, TurnStatus, GameStatus, Match, Character, BaseTurn
from core.contexts.turn_context import TurnContext
from core.contexts.match_context import MatchContext
from core.contexts.room_context import RoomContext
from core.contexts.character_context import CharacterContext
from services.game_state_service import GameStateService
from core.rules import RuleEngine
from ai.chains.story_gen import StoryResponse
from core.events import EventBus

logger = logging.getLogger(__name__)

class TurnService:
    """回合服务，协调回合转换相关的业务逻辑"""
    
    def __init__(self, game_state_service: GameStateService, rule_engine: RuleEngine = None, event_bus: EventBus = None):
        """初始化回合服务
        
        Args:
            game_state_service: GameStateService - 游戏状态服务
            rule_engine: RuleEngine - 规则引擎
            event_bus: EventBus - 事件总线
        """
        self.game_state_service = game_state_service
        self.rule_engine = rule_engine or RuleEngine()
        self.event_bus = event_bus
    
    def can_start_turn(self, turn_type: TurnType, match_context: MatchContext, active_players: List[str] = None) -> Tuple[bool, str]:
        """验证是否可以开始某类回合
        
        Args:
            turn_type: TurnType - 回合类型
            match_context: MatchContext - 游戏局控制器
            active_players: List[str] - 激活的玩家列表（仅对玩家回合有效）
            
        Returns:
            Tuple[bool, str]: (是否可以开始, 原因)
        """
        # 检查游戏状态
        if match_context.match.status != GameStatus.RUNNING and turn_type != TurnType.SYSTEM:
            return False, f"游戏未在运行中，当前状态: {match_context.match.status}"
        
        # 获取当前回合
        current_turn = None
        if match_context.match.current_turn_id:
            for turn in match_context.match.turns:
                if turn.id == match_context.match.current_turn_id:
                    current_turn = turn
                    break
        
        # 检查当前回合状态
        if current_turn and current_turn.status != TurnStatus.COMPLETED:
            return False, f"当前回合未完成，无法开始新回合"
        
        # 对于玩家回合，检查是否有激活玩家
        if turn_type == TurnType.PLAYER and (not active_players or len(active_players) == 0):
            return False, "玩家回合必须指定激活玩家"
            
        return True, "可以开始回合"
    
    def can_player_act(self, player_id: str, turn_context: TurnContext) -> Tuple[bool, str]:
        """验证玩家是否可以在当前回合行动
        
        Args:
            player_id: str - 玩家ID
            turn_context: TurnContext - 回合控制器
            
        Returns:
            Tuple[bool, str]: (是否可以行动, 原因)
        """
        turn = turn_context.turn
        
        # 检查回合类型
        if not isinstance(turn, (ActionTurn, DiceTurn)):
            return False, "当前不是玩家行动回合"
        
        # 检查回合状态
        if turn.status != TurnStatus.PENDING:
            return False, f"当前回合状态不允许行动: {turn.status}"
        
        # 检查玩家是否在激活列表中
        active_players = turn_context.get_active_players()
        if player_id not in active_players:
            return False, "你不在当前回合的激活玩家列表中"
        
        # 检查玩家是否已经行动过
        if isinstance(turn, ActionTurn):
            player_action = turn_context.get_player_action(player_id)
            if player_action:
                return False, "你已经在当前回合行动过了"
        
        if isinstance(turn, DiceTurn):
            dice_result = turn_context.get_player_dice_result(player_id)
            if dice_result:
                return False, "你已经在当前回合进行过骰子检定了"
            
        return True, "可以行动"
    
    async def transition_to_dm_turn(self, match_context: MatchContext, room_context: RoomContext) -> Tuple[TurnContext, List[Dict[str, str]]]:
        """转换到DM回合
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            
        Returns:
            Tuple[TurnContext, List[Dict[str, str]]]: (新的DM回合控制器, 通知消息列表)
        """
        messages = []
        
        # 完成当前回合（如果有）
        current_turn_id = match_context.match.current_turn_id
        if current_turn_id:
            for turn in match_context.match.turns:
                if turn.id == current_turn_id and turn.status != TurnStatus.COMPLETED:
                    turn_context = TurnContext(turn)
                    turn_context.complete_turn(TurnType.DM)
                    break
        
        # 创建新的DM回合
        dm_turn_context = TurnContext.create_dm_turn()
        
        # 将回合添加到游戏局
        match_context.match.turns.append(dm_turn_context.turn)
        match_context.set_current_turn(dm_turn_context.turn.id)
        
        logger.info(f"创建新的DM回合: ID={dm_turn_context.turn.id}")
        
        # 通知所有玩家
        for player in room_context.list_players():
            messages.append({
                "recipient": player.id,
                "content": "DM正在思考中..."
            })
        
        return dm_turn_context, messages
    
    async def transition_to_player_turn(self, match_context: MatchContext, room_context, 
                                       active_players: List[str], turn_mode: str = "action",
                                       difficulty: Optional[int] = None, 
                                       action_desc: Optional[str] = None) -> Tuple[TurnContext, List[Dict[str, str]]]:
        """转换到玩家回合
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            active_players: List[str] - 激活的玩家列表
            turn_mode: str - 回合模式，"action"或"dice"
            difficulty: Optional[int] - 骰子检定难度（仅在turn_mode为"dice"时有效）
            action_desc: Optional[str] - 行动描述（仅在turn_mode为"dice"时有效）
            
        Returns:
            Tuple[TurnContext, List[Dict[str, str]]]: (新的玩家回合控制器, 通知消息列表)
        """
        messages = []
        
        # 完成当前回合（如果有）
        current_turn_id = match_context.match.current_turn_id
        if current_turn_id:
            for turn in match_context.match.turns:
                if turn.id == current_turn_id and turn.status != TurnStatus.COMPLETED:
                    turn_context = TurnContext(turn)
                    turn_context.complete_turn(TurnType.PLAYER, active_players)
                    break
        
        # 创建新的玩家回合
        if turn_mode == "dice":
            if not difficulty:
                raise ValueError("掷骰子回合必须指定难度")
                
            turn_context = TurnContext.create_dice_turn(
                active_players=active_players,
                difficulty=difficulty,
                action_desc=action_desc or "行动"
            )
            
            logger.info(f"创建新的掷骰子回合: ID={turn_context.turn.id}, 难度={difficulty}, 行动描述={action_desc or '行动'}")
            
            # 通知所有玩家
            for player in room_context.list_players():
                if player.id in active_players:
                    messages.append({
                        "recipient": player.id,
                        "content": f"需要进行 {action_desc or '行动'} 的骰子检定，难度为 {difficulty}。请描述你的具体行动。"
                    })
                else:
                    messages.append({
                        "recipient": player.id,
                        "content": f"等待玩家进行 {action_desc or '行动'} 的骰子检定，难度为 {difficulty}。"
                    })
        else:
            turn_context = TurnContext.create_action_turn(
                active_players=active_players
            )
            
            logger.info(f"创建新的普通玩家回合: ID={turn_context.turn.id}")
            
            # 通知所有玩家
            for player in room_context.list_players():
                if player.id in active_players:
                    messages.append({
                        "recipient": player.id,
                        "content": "轮到你行动了，请输入你的行动。"
                    })
                else:
                    messages.append({
                        "recipient": player.id,
                        "content": "等待其他玩家行动..."
                    })
        
        # 将回合添加到游戏局
        match_context.match.turns.append(turn_context.turn)
        match_context.set_current_turn(turn_context.turn.id)
                
        return turn_context, messages
    
    async def process_player_action(self, player_id: str, action: str, turn_context: TurnContext, 
                                   match_context: MatchContext, character_context: Optional[CharacterContext] = None) -> Tuple[bool, List[Dict[str, str]]]:
        """处理玩家行动
        
        Args:
            player_id: str - 玩家ID
            action: str - 行动描述
            turn_context: TurnContext - 回合控制器
            match_context: MatchContext - 游戏局控制器
            character_context: Optional[CharacterContext] - 角色控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功处理, 通知消息列表)
        """
        messages = []
        
        # 验证玩家是否可以行动
        can_act, reason = self.can_player_act(player_id, turn_context)
        if not can_act:
            messages.append({"recipient": player_id, "content": reason})
            return False, messages
        
        # 处理玩家行动
        if isinstance(turn_context.turn, ActionTurn):
            # 普通行动回合：记录玩家行动
            success = turn_context.record_player_action(player_id, action)
            if not success:
                messages.append({"recipient": player_id, "content": "无法处理你的行动"})
                return False, messages
                
            # 通知玩家行动已记录
            messages.append({"recipient": player_id, "content": f"你的行动已记录: {action}"})
            
            logger.info(f"记录玩家行动: 玩家ID={player_id}, 行动={action}")
        
        elif isinstance(turn_context.turn, DiceTurn):
            # 掷骰子回合：进行掷骰子
            difficulty = turn_context.turn.difficulty
            
            # 使用规则引擎处理掷骰子
            success, roll = self.rule_engine.handle_dice_check(action, difficulty)
            
            # 记录掷骰子结果
            dice_success = turn_context.record_dice_result(player_id, roll, success, action)
            if not dice_success:
                messages.append({"recipient": player_id, "content": "无法处理你的骰子检定"})
                return False, messages
            
            # 如果判定失败，减少角色血量
            if not success and character_context:
                # 使用规则引擎计算失败伤害并应用
                health_change = self.rule_engine.calculate_failure_damage(difficulty)
                character_context.modify_health(health_change)
                
                # 通知玩家
                messages.append({
                    "recipient": player_id, 
                    "content": f"你的骰子检定失败，生命值减少 {abs(health_change)}，当前生命值: {character_context.character.health}/{character_context.character.max_health}"
                })
                
                logger.info(f"角色 {character_context.character.id} (玩家 {player_id}) 判定失败，生命值变化: {health_change}，当前生命值: {character_context.character.health}")
            else:
                # 通知玩家
                messages.append({
                    "recipient": player_id, 
                    "content": f"你的骰子检定 {'成功' if success else '失败'}，掷出了 {roll}，难度为 {difficulty}"
                })
            
            logger.info(f"玩家 {player_id} 尝试: {action}, 掷骰子结果: {roll}, 难度: {difficulty}, {'成功' if success else '失败'}")
        
        # 检查回合是否完成
        if turn_context.all_players_acted():
            turn_context.complete_turn()
            logger.info("所有玩家已行动，回合完成")
            
            # 如果是掷骰子回合，处理掷骰子结果
            if isinstance(turn_context.turn, DiceTurn):
                dice_results = self.process_dice_results(turn_context)
                
                # 构建结果消息
                result_message = "【掷骰子结果】\n"
                for result in dice_results:
                    player_name = result["player_id"]  # 这里应该从玩家列表中获取名称
                    result_message += f"{player_name} 尝试 {result['action']}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
                
                # 通知所有玩家
                for player in match_context.match.players:
                    messages.append({"recipient": player.id, "content": result_message})
        
        return True, messages
    
    def process_dice_results(self, turn_context: TurnContext) -> List[Dict[str, Any]]:
        """处理骰子结果
        
        Args:
            turn_context: TurnContext - 回合控制器
            
        Returns:
            List[Dict[str, Any]]: 处理后的结果列表
        """
        if not isinstance(turn_context.turn, DiceTurn):
            return []
            
        results = []
        for player_id, result in turn_context.turn.dice_results.items():
            results.append({
                "player_id": player_id,
                "roll": result["roll"],
                "success": result["success"],
                "difficulty": result["difficulty"],
                "action": result["action"]
            })
            
        return results
    
    async def set_dm_narration(self, turn_context: TurnContext, narration: str, match_context: MatchContext, room_context) -> List[Dict[str, str]]:
        """设置DM回合的叙述内容并通知玩家
        
        Args:
            turn_context: TurnContext - 回合控制器
            narration: str - 叙述内容
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            
        Returns:
            List[Dict[str, str]]: 通知消息列表
        """
        # 设置叙述内容
        turn_context.set_narration(narration)
        
        # 生成通知消息
        messages = []
        
        # 通知所有玩家
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": narration})
            
        logger.info(f"设置DM回合 {turn_context.turn.id} 的叙述内容")
        
        return messages
    
    async def handle_turn_transition(self, response: Union[Dict[str, Any], Any], turn_context: TurnContext, 
                                    match_context: MatchContext, room_context) -> List[Dict[str, str]]:
        """处理回合转换和通知玩家
        
        Args:
            response: Union[Dict[str, Any], Any] - AI响应
            turn_context: TurnContext - 当前回合控制器
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            
        Returns:
            List[Dict[str, str]]: 通知消息列表
        """
        messages = []
        
        # 从响应中提取信息
        narration = response.narration if hasattr(response, "narration") else ""
        active_players = response.active_players if hasattr(response, "active_players") else []
        need_dice_roll = response.need_dice_roll if hasattr(response, "need_dice_roll") else False
        difficulty = response.difficulty if hasattr(response, "difficulty") else None
        action_desc = response.action_desc if hasattr(response, "action_desc") else "行动"
        
        # 保存DM叙述到DMTurn对象
        if isinstance(turn_context.turn, DMTurn):
            turn_context.set_narration(narration)
        
        # 完成当前回合，准备下一个玩家回合
        turn_context.complete_turn(TurnType.PLAYER, active_players)
        
        # 根据是否需要骰子检定创建不同类型的回合
        if need_dice_roll and difficulty:
            # 创建新的掷骰子回合
            new_turn_context = TurnContext.create_dice_turn(
                active_players=active_players,
                difficulty=difficulty,
                action_desc=action_desc
            )
            
            # 将回合添加到游戏局
            match_context.match.turns.append(new_turn_context.turn)
            match_context.set_current_turn(new_turn_context.turn.id)
            
            # 通知所有玩家
            for player in room_context.list_players():
                messages.append({"recipient": player.id, "content": narration})
            
            # 通知激活玩家
            for player_id in active_players:
                messages.append({
                    "recipient": player_id, 
                    "content": f"需要进行 {action_desc} 的骰子检定，难度为 {difficulty}。请描述你的具体行动。"
                })
        else:
            # 创建新的普通玩家回合
            new_turn_context = TurnContext.create_action_turn(
                active_players=active_players
            )
            
            # 将回合添加到游戏局
            match_context.match.turns.append(new_turn_context.turn)
            match_context.set_current_turn(new_turn_context.turn.id)
            
            # 通知所有玩家
            for player in room_context.list_players():
                messages.append({"recipient": player.id, "content": narration})
            
            # 通知激活玩家
            for player_id in active_players:
                messages.append({
                    "recipient": player_id, 
                    "content": "轮到你行动了，请输入你的行动。"
                })
                
        return messages
    
    async def transition_to_system_turn(self, match_context: MatchContext, room_context: RoomContext, 
                                      system_type: SystemTurnType) -> Tuple[TurnContext, List[Dict[str, str]]]:
        """转换到系统回合
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            system_type: SystemTurnType - 系统回合类型
            
        Returns:
            Tuple[TurnContext, List[Dict[str, str]]]: (新的系统回合控制器, 通知消息列表)
        """
        messages = []
        
        # 完成当前回合（如果有）
        current_turn_id = match_context.match.current_turn_id
        if current_turn_id:
            for turn in match_context.match.turns:
                if turn.id == current_turn_id and turn.status != TurnStatus.COMPLETED:
                    turn_context = TurnContext(turn)
                    turn_context.complete_turn(TurnType.SYSTEM)
                    break
        
        # 创建新的系统回合
        system_turn_context = TurnContext.create_system_turn(system_type)
        
        # 将回合添加到游戏局
        match_context.match.turns.append(system_turn_context.turn)
        match_context.set_current_turn(system_turn_context.turn.id)
        
        logger.info(f"创建新的系统回合: ID={system_turn_context.turn.id}, 类型={system_type}")
        
        # 根据系统回合类型生成不同的通知消息
        if system_type == SystemTurnType.CHARACTER_SELECTION:
            # 角色选择回合通知
            for player in room_context.list_players():
                messages.append({
                    "recipient": player.id,
                    "content": "游戏正在初始化，请选择你的角色。"
                })
        elif system_type == SystemTurnType.GAME_SUMMARY:
            # 游戏总结回合通知
            summary = self._generate_game_summary(match_context)
            system_turn_context.set_system_data(summary)
            
            summary_message = "【游戏统计】\n" + summary.get("text", "游戏结束！")
            for player in room_context.list_players():
                messages.append({
                    "recipient": player.id,
                    "content": summary_message
                })
        
        return system_turn_context, messages
    
    def _generate_game_summary(self, match_context: MatchContext) -> Dict[str, Any]:
        """生成游戏总结数据
        
        Args:
            match_context: MatchContext - 游戏局控制器
            
        Returns:
            Dict[str, Any] - 游戏总结数据
        """
        # 统计游戏数据
        total_turns = len(match_context.match.turns)
        dm_turns = 0
        player_turns = 0
        system_turns = 0
        dice_turns = 0
        
        for turn in match_context.match.turns:
            if turn.turn_type == TurnType.DM:
                dm_turns += 1
            elif turn.turn_type == TurnType.PLAYER:
                player_turns += 1
                if hasattr(turn, 'dice_results'):
                    dice_turns += 1
            elif turn.turn_type == TurnType.SYSTEM:
                system_turns += 1
        
        # 统计角色状态
        characters_summary = []
        for character in match_context.match.characters:
            if character.player_id:  # 只统计玩家角色
                characters_summary.append({
                    "name": character.name,
                    "health": character.health,
                    "alive": character.alive,
                    "player_id": character.player_id
                })
        
        # 生成总结文本
        summary_text = f"游戏结束！\n"
        summary_text += f"总回合数: {total_turns}\n"
        summary_text += f"DM回合数: {dm_turns}\n"
        summary_text += f"玩家回合数: {player_turns}\n"
        summary_text += f"掷骰子回合数: {dice_turns}\n"
        
        summary_text += "\n角色状态:\n"
        for char in characters_summary:
            summary_text += f"{char['name']}: 生命值 {char['health']}, {'存活' if char['alive'] else '死亡'}\n"
        
        return {
            "text": summary_text,
            "stats": {
                "total_turns": total_turns,
                "dm_turns": dm_turns,
                "player_turns": player_turns,
                "dice_turns": dice_turns,
                "system_turns": system_turns
            },
            "characters": characters_summary
        }
    
    async def is_dm_turn(self, turn_context: TurnContext) -> bool:
        """检查当前回合是否为DM回合
        
        Args:
            turn_context: TurnContext - 回合控制器
            
        Returns:
            bool - 是否为DM回合
        """
        if not turn_context or not turn_context.turn:
            return False
            
        return turn_context.turn.turn_type == TurnType.DM
    
    async def is_player_turn(self, turn_context: TurnContext) -> bool:
        """检查当前回合是否为玩家回合
        
        Args:
            turn_context: TurnContext - 回合控制器
            
        Returns:
            bool - 是否为玩家回合
        """
        if not turn_context or not turn_context.turn:
            return False
            
        return turn_context.turn.turn_type == TurnType.PLAYER
    
    async def is_system_turn(self, turn_context: TurnContext) -> bool:
        """检查当前回合是否为系统回合
        
        Args:
            turn_context: TurnContext - 回合控制器
            
        Returns:
            bool - 是否为系统回合
        """
        if not turn_context or not turn_context.turn:
            return False
            
        return turn_context.turn.turn_type == TurnType.SYSTEM
    
    async def is_turn_completed(self, turn_context: TurnContext) -> bool:
        """检查当前回合是否已完成
        
        Args:
            turn_context: TurnContext - 回合控制器
            
        Returns:
            bool - 是否已完成
        """
        if not turn_context or not turn_context.turn:
            return False
            
        return turn_context.turn.status == TurnStatus.COMPLETED

    async def get_turn_context(self, match_context: MatchContext) -> Optional[TurnContext]:
        """获取当前回合控制器
        
        Args:
            match_context: MatchContext - 游戏局控制器
            
        Returns:
            Optional[TurnContext] - 回合控制器，如果不存在则返回None
        """
        if not match_context.match.current_turn_id:
            return None
            
        for turn in match_context.match.turns:
            if turn.id == match_context.match.current_turn_id:
                return TurnContext(turn)
                
        return None

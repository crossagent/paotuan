import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus, SystemTurnType
from core.contexts.match_context import MatchContext
from core.contexts.character_context import CharacterContext
from core.contexts.room_context import RoomContext
from core.contexts.turn_context import TurnContext
from models.scenario import Scenario
from services.game_state_service import GameStateService
from services.turn_service import TurnService
from utils.scenario_loader import ScenarioLoader
from core.rules import RuleEngine
from core.events import EventBus

logger = logging.getLogger(__name__)

class MatchService:
    """游戏局服务，协调游戏局相关的业务逻辑"""
    
    def __init__(self, game_state_service: GameStateService, 
                scenario_loader: ScenarioLoader = None, rule_engine: RuleEngine = None, 
                event_bus: EventBus = None):
        """初始化游戏局服务
        
        Args:
            game_state_service: GameStateService - 游戏状态服务
            scenario_loader: ScenarioLoader - 剧本加载器
            rule_engine: RuleEngine - 规则引擎
            event_bus: EventBus - 事件总线
        """
        self.game_state_service = game_state_service
        self.scenario_loader = scenario_loader or ScenarioLoader()
        self.rule_engine = rule_engine or RuleEngine()
        self.event_bus = event_bus
    
    async def create_match(self, room_context: RoomContext) -> Tuple[MatchContext, List[Dict[str, str]]]:
        """创建新的游戏局
        
        Args:
            room_context: RoomContext - 房间控制器
            scene: str - 游戏局场景名称
            
        Returns:
            Tuple[MatchContext, List[Dict[str, str]]]: (游戏局控制器, 通知消息列表)
        """
        # 检查是否有进行中的游戏局
        if room_context.room.current_match_id:
            for match in room_context.room.matches:
                if match.id == room_context.room.current_match_id and match.status == GameStatus.RUNNING:
                    error_msg = "当前已有进行中的游戏局，无法创建新游戏局"
                    logger.warning(error_msg)
                    return None, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        scene = room_context.get_scenario_id()

        # 创建新游戏局
        match_context = MatchContext.create_match(scene)
        
        # 将游戏局添加到房间
        room_context.room.matches.append(match_context.match)
        room_context.set_current_match(match_context.match.id)
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        create_message = f"创建了新的游戏局: {scene}"
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": create_message})
        
        logger.info(f"创建新游戏局: {scene} (ID: {match_context.match.id})")

        # 创建角色选择系统回合
        messages = []

        # 通知房间中的所有玩家
        start_message = f"游戏开始！剧本: {match_context.match.scenario_id}"
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": start_message})        

        return match_context, messages
    
    async def start_match(self, match_context: MatchContext, room_context:RoomContext) -> Tuple[bool, List[Dict[str, str]]]:
        """开始游戏局
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功开始游戏局, 通知消息列表)
        """
        # 检查是否已设置剧本
        if not match_context.match.scenario_id:
            error_msg = "无法开始游戏局: 未设置剧本"
            logger.warning(error_msg)
            return False, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 检查所有玩家是否都已选择角色
        all_selected, players_without_characters = await self.check_all_players_selected_character(match_context, room_context)
                
        if not all_selected:
            player_names = ", ".join(players_without_characters)
            error_msg = f"无法开始游戏局: 以下玩家未选择角色: {player_names}"
            logger.warning(error_msg)
            return False, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 使用MatchContext开始游戏局
        success = match_context.start_match()
        
        if not success:
            error_msg = "开始游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        messages = []
        
        logger.info(f"游戏局开始: ID={match_context.match.id}, 剧本={match_context.match.scenario_id}")
        return True, messages
    
    async def end_match(self, match_context: MatchContext, room_context, result: Optional[str] = None) -> Tuple[bool, List[Dict[str, str]]]:
        """结束游戏局
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            result: Optional[str] - 游戏结果
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功结束游戏局, 通知消息列表)
        """
        # 创建游戏总结系统回合
        messages = []
        if self.turn_service:
            # 创建游戏总结系统回合
            system_turn_context, system_messages = await self.turn_service.transition_to_system_turn(
                match_context=match_context,
                room_context=room_context,
                system_type=SystemTurnType.GAME_SUMMARY
            )
            
            # 完成系统回合
            system_turn_context.complete_turn()
            
            # 添加系统回合的消息
            messages.extend(system_messages)
        
        # 使用MatchContext结束游戏局
        success = match_context.end_match(result)
        
        if not success:
            error_msg = "结束游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 通知房间中的所有玩家
        end_message = f"游戏结束！" + (f"结果: {result}" if result else "")
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": end_message})
        
        logger.info(f"游戏局结束: ID={match_context.match.id}, 结果={result or '未知'}")
        return True, messages
    
    async def pause_match(self, match_context: MatchContext, room_context) -> Tuple[bool, List[Dict[str, str]]]:
        """暂停游戏局
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功暂停游戏局, 通知消息列表)
        """
        # 使用MatchContext暂停游戏局
        success = match_context.pause_match()
        
        if not success:
            error_msg = "暂停游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        pause_message = "游戏已暂停"
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": pause_message})
        
        logger.info(f"游戏局暂停: ID={match_context.match.id}")
        return True, messages
    
    async def resume_match(self, match_context: MatchContext, room_context) -> Tuple[bool, List[Dict[str, str]]]:
        """恢复游戏局
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功恢复游戏局, 通知消息列表)
        """
        # 使用MatchContext恢复游戏局
        success = match_context.resume_match()
        
        if not success:
            error_msg = "恢复游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        resume_message = "游戏已恢复"
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": resume_message})
        
        logger.info(f"游戏局恢复: ID={match_context.match.id}")
        return True, messages
    
    async def set_scenario(self, match_context: MatchContext, room_context, scenario_id: str) -> Tuple[bool, Optional[str], List[Dict[str, str]]]:
        """设置剧本
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            scenario_id: str - 剧本ID
            
        Returns:
            Tuple[bool, Optional[str], List[Dict[str, str]]]: (是否成功设置剧本, 错误消息, 通知消息列表)
        """
        # 检查剧本是否存在
        scenario = self.scenario_loader.load_scenario(scenario_id)
        if not scenario:
            error_msg = f"剧本不存在: {scenario_id}"
            logger.warning(error_msg)
            return False, error_msg, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 检查剧本是否适合当前房间人数
        current_player_count = len(room_context.list_players())
        
        # 检查剧本最小玩家数限制
        if hasattr(scenario, 'min_players') and current_player_count < scenario.min_players:
            error_msg = f"当前房间人数({current_player_count})不足，该剧本至少需要{scenario.min_players}名玩家"
            logger.warning(f"无法设置剧本: {error_msg}")
            return False, error_msg, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 检查剧本最大玩家数限制
        if hasattr(scenario, 'max_players') and current_player_count > scenario.max_players:
            error_msg = f"当前房间人数({current_player_count})超过剧本上限，该剧本最多支持{scenario.max_players}名玩家"
            logger.warning(f"无法设置剧本: {error_msg}")
            return False, error_msg, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 使用MatchContext设置剧本
        success = match_context.set_scenario(scenario_id)
        
        if not success:
            error_msg = "设置剧本失败: 游戏局已经开始"
            logger.warning(error_msg)
            return False, error_msg, [{"recipient": room_context.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        scenario_message = f"剧本已设置为: {scenario_id}"
        for player in room_context.list_players():
            messages.append({"recipient": player.id, "content": scenario_message})
        
        # 加载可选角色列表
        available_characters = self.load_available_characters(scenario)
        match_context.set_available_characters(available_characters)
        
        # 通知玩家可选角色
        if available_characters:
            character_names = ", ".join([char.get("name", "未知") for char in available_characters])
            character_message = f"可选角色: {character_names}"
            for player in room_context.list_players():
                messages.append({"recipient": player.id, "content": character_message})
        
        logger.info(f"设置剧本: 游戏局ID={match_context.match.id}, 剧本ID={scenario_id}")
        return True, None, messages
    
    def load_available_characters(self, scenario: Scenario) -> List[Dict[str, Any]]:
        """从剧本中加载可选角色列表
        
        Args:
            scenario - 剧本对象
            
        Returns:
            List[Dict[str, Any]] - 可选角色列表
        """
        available_characters = []
        
        # 从剧本中提取角色信息
        if hasattr(scenario, "characters") and scenario.characters:
            for char in scenario.characters:
                if hasattr(char, "name") and char.name:
                    available_characters.append({
                        "name": char.name,
                        "description": getattr(char, "description", ""),
                        "is_main": getattr(char, "is_main", True),
                        "attributes": {}
                    })
        
        # 如果没有角色，尝试从重要角色中提取
        if not available_characters and hasattr(scenario, "important_characters"):
            for char_type, chars in scenario.important_characters.items():
                for char in chars:
                    if isinstance(char, dict) and "角色名称" in char:
                        available_characters.append({
                            "name": char["角色名称"],
                            "description": char.get("描述", ""),
                            "is_main": char_type == "主要角色",
                            "attributes": {}
                        })
        
        # 如果还是没有角色，尝试从character_templates中提取
        if not available_characters and hasattr(scenario, "character_templates"):
            for template in scenario.character_templates:
                available_characters.append({
                    "name": template.name,
                    "description": template.description if hasattr(template, "description") else "",
                    "occupation": template.occupation if hasattr(template, "occupation") else "",
                    "is_main": True,
                    "attributes": {}
                })
                
        return available_characters
    
    async def select_character(self, match_context: MatchContext, room_context, player_id: str, character_name: str) -> Tuple[bool, str, List[Dict[str, str]]]:
        """玩家选择角色
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器
            player_id: str - 玩家ID
            character_name: str - 角色名称
            
        Returns:
            Tuple[bool, str, List[Dict[str, str]]]: (是否选择成功, 消息, 通知消息列表)
        """
        # 检查游戏状态，只允许在游戏开始前（WAITING状态）选择角色
        if match_context.match.status != GameStatus.WAITING:
            error_msg = "游戏已经开始，无法更换角色"
            return False, error_msg, [{"recipient": player_id, "content": error_msg}]
            
        # 检查剧本是否已设置
        if not match_context.match.scenario_id:
            error_msg = "请先设置剧本再选择角色"
            return False, error_msg, [{"recipient": player_id, "content": error_msg}]
            
        # 检查可选角色列表是否为空
        if not match_context.match.available_characters:
            error_msg = "当前剧本没有可选角色"
            return False, error_msg, [{"recipient": player_id, "content": error_msg}]
            
        # 查找玩家
        player = room_context.get_player_by_id(player_id)
        if not player:
            error_msg = "找不到玩家"
            return False, error_msg, []
            
        # 查找角色
        selected_character_info = None
        for char_info in match_context.match.available_characters:
            if char_info.get("name") == character_name:
                selected_character_info = char_info
                break
                
        if not selected_character_info:
            available_chars = ", ".join([c.get("name", "未知") for c in match_context.match.available_characters])
            error_msg = f"找不到角色: {character_name}。可选角色: {available_chars}"
            return False, error_msg, [{"recipient": player_id, "content": error_msg}]
            
        # 检查角色是否已被选择
        for character in match_context.match.characters:
            if character.name == character_name and character.player_id is not None and character.player_id != player_id:
                error_msg = f"角色 {character_name} 已被其他玩家选择"
                return False, error_msg, [{"recipient": player_id, "content": error_msg}]
                
        # 如果玩家已有角色，先解除绑定
        if player.character_id:
            old_character = match_context.get_character(player.character_id)
            if old_character:
                old_character.player_id = None
                logger.info(f"解除玩家 {player.name} 与角色 {old_character.name} 的绑定")
                
        # 创建新角色或使用现有角色
        character_exists = False
        character_id = None
        
        for character in match_context.match.characters:
            if character.name == character_name and character.player_id is None:
                character.player_id = player_id
                character_id = character.id
                character_exists = True
                logger.info(f"玩家 {player.name} 选择了现有角色 {character_name}")
                break
                
        if not character_exists:
            # 创建新角色
            character_context = CharacterContext.create_character(
                name=character_name,
                player_id=player_id,
                attributes=selected_character_info.get("attributes", {})
            )
            
            # 添加角色到游戏局
            match_context.add_character(character_context.character)
            character_id = character_context.character.id
            
            logger.info(f"玩家 {player.name} 选择了角色 {character_name}，创建角色ID: {character_id}")
            
        # 关联玩家和角色
        room_context.set_player_character(player_id, character_id)
        
        # 更新玩家-角色映射
        self.game_state_service.update_player_character_mapping(player_id, character_id)
            
        # 生成通知消息
        messages = []
        
        # 通知玩家选择结果
        messages.append({"recipient": player_id, "content": f"成功选择角色: {character_name}"})
        
        # 通知房间中的其他玩家
        select_message = f"玩家 {player.name} 选择了角色 {character_name}"
        for p in room_context.list_players():
            if p.id != player_id:
                messages.append({"recipient": p.id, "content": select_message})
                
        return True, f"成功选择角色: {character_name}", messages
    
    async def check_all_players_selected_character(self, match_context: MatchContext, room_context: RoomContext = None) -> Tuple[bool, List[str]]:
        """检查是否所有玩家都已选择角色
        
        Args:
            match_context: MatchContext - 游戏局控制器
            room_context: RoomContext - 房间控制器，可选
            
        Returns:
            Tuple[bool, List[str]]: (是否所有玩家都已选择角色, 未选择角色的玩家名称列表)
        """
        if not room_context:
            # 如果没有提供房间控制器，尝试从游戏状态服务获取
            room_id = None
            for room in self.game_state_service.list_rooms():
                if room.current_match_id == match_context.match.id:
                    room_id = room.id
                    break
                    
            if not room_id:
                logger.warning(f"无法检查玩家角色选择状态: 找不到关联的房间")
                return False, ["未知玩家"]
                
            room = self.game_state_service.get_room(room_id)
            if not room:
                logger.warning(f"无法检查玩家角色选择状态: 找不到房间 {room_id}")
                return False, ["未知玩家"]
                
            room_context = RoomContext(room)
            
        # 检查所有玩家是否都已选择角色
        players_without_characters = []
        for player in room_context.list_players():
            if not player.character_id:
                players_without_characters.append(player.name)
                
        return len(players_without_characters) == 0, players_without_characters
    
    async def is_match_running(self, match_context: MatchContext) -> bool:
        """检查游戏局是否在运行中
        
        Args:
            match_context: MatchContext - 游戏局控制器
            
        Returns:
            bool - 是否在运行中
        """
        return match_context.match.status == GameStatus.RUNNING
    
    async def get_character_context_by_player_id(self, match_context: MatchContext, player_id: str) -> Optional[CharacterContext]:
        """根据玩家ID获取角色控制器
        
        Args:
            match_context: MatchContext - 游戏局控制器
            player_id: str - 玩家ID
            
        Returns:
            Optional[CharacterContext] - 角色控制器，如果不存在则返回None
        """
        character = match_context.get_character_by_player_id(player_id)
        if character:
            return CharacterContext(character)
        return None
    
    async def get_match_context(self, room_context:RoomContext) -> Optional[MatchContext]:
        """获取当前游戏局控制器
        
        Args:
            room_context: RoomContext - 房间控制器
            
        Returns:
            Optional[MatchContext] - 游戏局控制器，如果不存在则返回None
        """
        if not room_context.room.current_match_id:
            return None
            
        for match in room_context.room.matches:
            if match.id == room_context.room.current_match_id:
                return MatchContext(match)
                
        return None

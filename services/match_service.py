import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus
from core.controllers.match_controller import MatchController
from utils.scenario_loader import ScenarioLoader
from core.rules import RuleEngine

logger = logging.getLogger(__name__)

class MatchService:
    """游戏局服务，处理游戏局相关的业务逻辑"""
    
    def __init__(self, scenario_loader: ScenarioLoader = None, rule_engine: RuleEngine = None, event_bus=None):
        """初始化游戏局服务
        
        Args:
            scenario_loader: 剧本加载器
            rule_engine: 规则引擎
            event_bus: 事件总线，用于发布事件和消息
        """
        self.scenario_loader = scenario_loader or ScenarioLoader()
        self.rule_engine = rule_engine or RuleEngine()
        self.event_bus = event_bus
    
    async def create_match(self, room: Room, game_instance, name: str = "新的冒险") -> Tuple[MatchController, List[Dict[str, str]]]:
        """创建新的游戏局
        
        Args:
            room: 房间对象
            game_instance: 游戏实例
            name: 游戏局名称
            
        Returns:
            Tuple[MatchController, List[Dict[str, str]]]: 创建的游戏局控制器和通知消息列表
        """
        # 检查是否有进行中的游戏局
        current_match_controller = MatchController.get_current_match_controller(room, game_instance)
        if current_match_controller and current_match_controller.match.status == GameStatus.RUNNING:
            error_msg = "当前已有进行中的游戏局，无法创建新游戏局"
            logger.warning(error_msg)
            return None, [{"recipient": room.host_id, "content": error_msg}]
        
        # 创建新游戏局
        match_controller = MatchController.create_match(room, game_instance, name)
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        create_message = f"创建了新的游戏局: {name}"
        for player in room.players:
            messages.append({"recipient": player.id, "content": create_message})
        
        # 游戏局创建完成
            
        logger.info(f"创建新游戏局: {name} (ID: {match_controller.match.id})")
        return match_controller, messages
    
    async def start_match(self, match_controller: MatchController) -> Tuple[bool, List[Dict[str, str]]]:
        """开始游戏局
        
        Args:
            match_controller: 游戏局控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功开始游戏局, 通知消息列表)
        """
        # 检查是否已设置剧本
        if not match_controller.match.scenario_id:
            error_msg = "无法开始游戏局: 未设置剧本"
            logger.warning(error_msg)
            return False, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 检查所有玩家是否都已选择角色
        all_selected, players_without_characters = match_controller.check_all_players_selected_character()
        if not all_selected:
            player_names = ", ".join(players_without_characters)
            error_msg = f"无法开始游戏局: 以下玩家未选择角色: {player_names}"
            logger.warning(error_msg)
            return False, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 使用MatchController开始游戏局
        success = match_controller.start_match()
        
        if not success:
            error_msg = "开始游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        start_message = f"游戏开始！剧本: {match_controller.match.scenario_id}"
        for player in match_controller.room.players:
            messages.append({"recipient": player.id, "content": start_message})
        
        # 游戏局开始
            
        logger.info(f"游戏局开始: ID={match_controller.match.id}, 剧本={match_controller.match.scenario_id}")
        return True, messages
    
    async def end_match(self, match_controller: MatchController, result: Optional[str] = None) -> Tuple[bool, List[Dict[str, str]]]:
        """结束游戏局
        
        Args:
            match_controller: 游戏局控制器
            result: 游戏结果
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功结束游戏局, 通知消息列表)
        """
        # 使用MatchController结束游戏局
        success = match_controller.end_match(result)
        
        if not success:
            error_msg = "结束游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        end_message = f"游戏结束！" + (f"结果: {result}" if result else "")
        for player in match_controller.room.players:
            messages.append({"recipient": player.id, "content": end_message})
        
        # 游戏局结束
            
        logger.info(f"游戏局结束: ID={match_controller.match.id}, 结果={result or '未知'}")
        return True, messages
    
    async def pause_match(self, match_controller: MatchController) -> Tuple[bool, List[Dict[str, str]]]:
        """暂停游戏局
        
        Args:
            match_controller: 游戏局控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功暂停游戏局, 通知消息列表)
        """
        # 使用MatchController暂停游戏局
        success = match_controller.pause_match()
        
        if not success:
            error_msg = "暂停游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        pause_message = "游戏已暂停"
        for player in match_controller.room.players:
            messages.append({"recipient": player.id, "content": pause_message})
        
        # 游戏局暂停
            
        logger.info(f"游戏局暂停: ID={match_controller.match.id}")
        return True, messages
    
    async def resume_match(self, match_controller: MatchController) -> Tuple[bool, List[Dict[str, str]]]:
        """恢复游戏局
        
        Args:
            match_controller: 游戏局控制器
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功恢复游戏局, 通知消息列表)
        """
        # 使用MatchController恢复游戏局
        success = match_controller.resume_match()
        
        if not success:
            error_msg = "恢复游戏局失败"
            logger.warning(error_msg)
            return False, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        resume_message = "游戏已恢复"
        for player in match_controller.room.players:
            messages.append({"recipient": player.id, "content": resume_message})
        
        # 游戏局恢复
            
        logger.info(f"游戏局恢复: ID={match_controller.match.id}")
        return True, messages
    
    async def set_scenario(self, match_controller: MatchController, scenario_id: str) -> Tuple[bool, Optional[str], List[Dict[str, str]]]:
        """设置剧本
        
        Args:
            match_controller: 游戏局控制器
            scenario_id: 剧本ID
            
        Returns:
            Tuple[bool, Optional[str], List[Dict[str, str]]]: (是否成功设置剧本, 错误消息, 通知消息列表)
        """
        # 检查剧本是否存在
        scenario = self.scenario_loader.load_scenario(scenario_id)
        if not scenario:
            error_msg = f"剧本不存在: {scenario_id}"
            logger.warning(error_msg)
            return False, error_msg, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 使用MatchController设置剧本
        success, error_msg = match_controller.set_scenario(scenario_id)
        
        if not success:
            logger.warning(f"设置剧本失败: {error_msg}")
            return False, error_msg, [{"recipient": match_controller.room.host_id, "content": error_msg}]
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        scenario_message = f"剧本已设置为: {scenario_id}"
        for player in match_controller.room.players:
            messages.append({"recipient": player.id, "content": scenario_message})
        
        # 加载可选角色列表
        available_characters = match_controller.load_available_characters()
        
        # 通知玩家可选角色
        if available_characters:
            character_names = ", ".join([char.get("name", "未知") for char in available_characters])
            character_message = f"可选角色: {character_names}"
            for player in match_controller.room.players:
                messages.append({"recipient": player.id, "content": character_message})
        
        # 剧本设置成功
            
        logger.info(f"设置剧本: 游戏局ID={match_controller.match.id}, 剧本ID={scenario_id}")
        return True, None, messages
    
    async def load_available_characters(self, match_controller: MatchController) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """加载可选角色列表
        
        Args:
            match_controller: 游戏局控制器
            
        Returns:
            Tuple[List[Dict[str, Any]], List[Dict[str, str]]]: (可选角色列表, 通知消息列表)
        """
        # 使用MatchController加载可选角色列表
        available_characters = match_controller.load_available_characters()
        
        # 生成通知消息
        messages = []
        
        # 通知玩家可选角色
        if available_characters:
            character_names = ", ".join([char.get("name", "未知") for char in available_characters])
            character_message = f"可选角色: {character_names}"
            for player in match_controller.room.players:
                messages.append({"recipient": player.id, "content": character_message})
        else:
            error_msg = "无法加载可选角色列表"
            for player in match_controller.room.players:
                messages.append({"recipient": player.id, "content": error_msg})
        
        logger.info(f"加载可选角色列表: 游戏局ID={match_controller.match.id}, 角色数量={len(available_characters)}")
        return available_characters, messages

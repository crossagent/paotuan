from typing import Dict, List, Optional, Any, Tuple, Union
import uuid
import logging
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus, Turn, TurnType, TurnStatus
from core.events import EventBus
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent

logger = logging.getLogger(__name__)

class GameInstance:
    """游戏实例，管理多个房间"""
    
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.rooms: Dict[str, Room] = {}
        self.event_bus = EventBus()
        self.player_room_map: Dict[str, str] = {}  # player_id -> room_id
        self.player_character_map: Dict[str, str] = {}  # player_id -> character_id
        
    def get_available_scenarios(self) -> List[Dict[str, str]]:
        """获取可用的剧本列表
        
        Returns:
            剧本列表，每个剧本包含id和name
        """
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        return scenario_loader.list_scenarios()
    
    def set_room_scenario(self, room_id: str, scenario_id: str) -> Tuple[bool, str]:
        """为指定房间设置剧本
        
        Args:
            room_id: 房间ID
            scenario_id: 剧本ID
            
        Returns:
            (是否设置成功, 消息)
        """
        room = self.get_room(room_id)
        if not room:
            return False, f"房间不存在: {room_id}"
            
        # 检查剧本是否存在
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        
        if not scenario:
            return False, f"剧本不存在: {scenario_id}"
            
        # 获取当前游戏局
        if not room.current_match_id:
            return False, "当前没有进行中的游戏局"
            
        for match in room.matches:
            if match.id == room.current_match_id:
                # 设置剧本ID和场景
                match.scenario_id = scenario_id
                match.scene = scenario.scene
                logger.info(f"为房间 {room.name} 设置剧本: {scenario.name}")
                return True, f"成功设置剧本: {scenario.name}"
                
        return False, "找不到当前游戏局"
        
    def create_room(self, name: str) -> Room:
        """创建新房间"""
        room_id = str(uuid.uuid4())
        room = Room(id=room_id, name=name)
        self.rooms[room_id] = room
        logger.info(f"创建房间: {name} (ID: {room_id})")
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """获取房间"""
        return self.rooms.get(room_id)
        
    def list_rooms(self) -> List[Room]:
        """列出所有房间"""
        return list(self.rooms.values())
        
    def get_player_room(self, player_id: str) -> Optional[Room]:
        """根据玩家ID获取所在房间
        
        Args:
            player_id: 玩家ID
            
        Returns:
            玩家所在的房间，如果玩家不在任何房间则返回None
        """
        room_id = self.player_room_map.get(player_id)
        if not room_id:
            return None
        return self.get_room(room_id)
    
    def get_player_match(self, player_id: str) -> Optional[Match]:
        """根据玩家ID获取当前活跃Match
        
        Args:
            player_id: 玩家ID
            
        Returns:
            玩家当前的游戏局，如果玩家不在任何房间或房间没有活跃游戏局则返回None
        """
        room = self.get_player_room(player_id)
        if not room or not room.current_match_id:
            return None
            
        for match in room.matches:
            if match.id == room.current_match_id:
                return match
        return None

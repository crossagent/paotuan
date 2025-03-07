import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus
from core.game_state import GameState
from core.events import EventBus

logger = logging.getLogger(__name__)

class GameService:
    """游戏服务，负责管理全局游戏状态和资源"""
    
    def __init__(self, game_state: GameState, event_bus: Optional[EventBus] = None):
        """初始化游戏服务
        
        Args:
            game_state: GameState - 游戏状态
            event_bus: Optional[EventBus] - 事件总线
        """
        self.game_state = game_state
        self.event_bus = event_bus
        
    def register_room(self, room_id: str, room: Room) -> None:
        """注册房间到游戏状态
        
        Args:
            room_id: str - 房间ID
            room: Room - 房间实体
        """
        self.game_state.rooms[room_id] = room
        logger.info(f"注册房间: ID={room_id}, 名称={room.name}")
        
    def unregister_room(self, room_id: str) -> bool:
        """从游戏状态中注销房间
        
        Args:
            room_id: str - 房间ID
            
        Returns:
            bool - 是否成功注销
        """
        if room_id in self.game_state.rooms:
            room = self.game_state.rooms.pop(room_id)
            logger.info(f"注销房间: ID={room_id}, 名称={room.name}")
            
            # 清理相关映射
            players_to_remove = []
            for player_id, mapped_room_id in self.game_state.player_room_map.items():
                if mapped_room_id == room_id:
                    players_to_remove.append(player_id)
                    
            for player_id in players_to_remove:
                if player_id in self.game_state.player_room_map:
                    del self.game_state.player_room_map[player_id]
                    logger.info(f"清理玩家-房间映射: 玩家ID={player_id}")
                    
                if player_id in self.game_state.player_character_map:
                    del self.game_state.player_character_map[player_id]
                    logger.info(f"清理玩家-角色映射: 玩家ID={player_id}")
                    
            return True
        return False
        
    def get_room(self, room_id: str) -> Optional[Room]:
        """获取房间
        
        Args:
            room_id: str - 房间ID
            
        Returns:
            Optional[Room] - 房间实体，如果不存在则返回None
        """
        return self.game_state.rooms.get(room_id)
        
    def list_rooms(self) -> List[Room]:
        """获取所有房间
        
        Returns:
            List[Room] - 所有房间列表
        """
        return list(self.game_state.rooms.values())
        
    def get_player_room(self, player_id: str) -> Optional[Room]:
        """获取玩家所在的房间
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[Room] - 玩家所在的房间，如果不存在则返回None
        """
        room_id = self.game_state.player_room_map.get(player_id)
        if room_id:
            return self.get_room(room_id)
        return None
        
    def update_player_room_mapping(self, player_id: str, room_id: Optional[str]) -> None:
        """更新玩家-房间映射
        
        Args:
            player_id: str - 玩家ID
            room_id: Optional[str] - 房间ID，如果为None则移除映射
        """
        if room_id is None:
            if player_id in self.game_state.player_room_map:
                del self.game_state.player_room_map[player_id]
                logger.info(f"移除玩家-房间映射: 玩家ID={player_id}")
        else:
            self.game_state.player_room_map[player_id] = room_id
            logger.info(f"更新玩家-房间映射: 玩家ID={player_id}, 房间ID={room_id}")
            
    def get_player_character(self, player_id: str) -> Optional[str]:
        """获取玩家的角色ID
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[str] - 角色ID，如果不存在则返回None
        """
        return self.game_state.player_character_map.get(player_id)
        
    def update_player_character_mapping(self, player_id: str, character_id: Optional[str]) -> None:
        """更新玩家-角色映射
        
        Args:
            player_id: str - 玩家ID
            character_id: Optional[str] - 角色ID，如果为None则移除映射
        """
        if character_id is None:
            if player_id in self.game_state.player_character_map:
                del self.game_state.player_character_map[player_id]
                logger.info(f"移除玩家-角色映射: 玩家ID={player_id}")
        else:
            self.game_state.player_character_map[player_id] = character_id
            logger.info(f"更新玩家-角色映射: 玩家ID={player_id}, 角色ID={character_id}")
            
    def get_character_by_player_id(self, player_id: str) -> Optional[Character]:
        """根据玩家ID获取角色
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[Character] - 角色实体，如果不存在则返回None
        """
        character_id = self.get_player_character(player_id)
        if not character_id:
            return None
            
        # 查找玩家所在房间
        room = self.get_player_room(player_id)
        if not room:
            return None
            
        # 获取当前游戏局
        current_match = None
        if room.current_match_id:
            for match in room.matches:
                if match.id == room.current_match_id:
                    current_match = match
                    break
                    
        if not current_match:
            return None
            
        # 在游戏局中查找角色
        for character in current_match.characters:
            if character.id == character_id:
                return character
                
        return None
        
    def is_player_in_room(self, player_id: str, room_id: str) -> bool:
        """检查玩家是否在指定房间中
        
        Args:
            player_id: str - 玩家ID
            room_id: str - 房间ID
            
        Returns:
            bool - 是否在房间中
        """
        mapped_room_id = self.game_state.player_room_map.get(player_id)
        return mapped_room_id == room_id

from typing import Dict, List, Optional, Any
import uuid
import logging
from datetime import datetime

from models.entities import Room, Match, Player, GameStatus, Turn, TurnType, TurnStatus
from core.events import EventBus
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent

logger = logging.getLogger(__name__)

class GameInstance:
    """游戏实例，管理多个房间"""
    
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.rooms: Dict[str, Room] = {}
        self.event_bus = EventBus()
        
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

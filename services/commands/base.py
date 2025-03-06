import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import Room, Match
from core.game import GameInstance
from core.room import RoomManager
from core.rules import RuleEngine
from core.events import EventBus
from adapters.base import GameEvent

logger = logging.getLogger(__name__)

class GameCommand:
    """游戏命令基类"""
    
    def __init__(self, game_instance: GameInstance, event_bus: EventBus, 
                 ai_service: Any, rule_engine: RuleEngine):
        self.game_instance = game_instance
        self.event_bus = event_bus
        self.ai_service = ai_service
        self.rule_engine = rule_engine
        
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令，返回事件或消息列表"""
        raise NotImplementedError("子类必须实现execute方法")
        
    def _get_or_create_room(self) -> Room:
        """获取或创建房间，公共方法"""
        rooms = self.game_instance.list_rooms()
        if not rooms:
            return self.game_instance.create_room("默认房间")
        return rooms[0]
        
    def _get_room_by_id(self, room_id: str) -> Optional[Room]:
        """根据ID获取房间"""
        return self.game_instance.get_room(room_id)
        
    def _get_player_room(self, player_id: str) -> Optional[Room]:
        """获取玩家所在的房间"""
        return self.game_instance.get_player_room(player_id)
        
    def _get_player_current_match(self, player_id: str) -> Optional[Match]:
        """获取玩家当前的游戏局"""
        return self.game_instance.get_player_match(player_id)

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class GameEvent:
    """游戏事件基类"""
    def __init__(self, event_type: str, data: Dict[str, Any] = None):
        self.event_type = event_type
        self.data = data or {}

class PlayerJoinedEvent(GameEvent):
    """玩家加入事件"""
    def __init__(self, player_id: str, player_name: str):
        super().__init__(
            event_type="PLAYER_JOINED",
            data={
                "player_id": player_id,
                "player_name": player_name
            }
        )

class PlayerRequestStartEvent(GameEvent):
    """DM决定开启游戏事件"""
    def __init__(self, player_id: str, player_name: str):
        super().__init__(
            event_type="START_MATCH",
            data={
                "player_id": player_id,
                "player_name": player_name
            }
        )

class PlayerActionEvent(GameEvent):
    """玩家行动事件"""
    def __init__(self, player_id: str, action: str):
        super().__init__(
            event_type="PLAYER_ACTION",
            data={
                "player_id": player_id,
                "action": action
            }
        )

class DMNarrationEvent(GameEvent):
    """DM叙述事件"""
    def __init__(self, narration: str, room_id: str = None):
        super().__init__(
            event_type="DM_NARRATION",
            data={
                "narration": narration,
                "room_id": room_id
            }
        )

class SetScenarioEvent(GameEvent):
    """设置剧本事件"""
    def __init__(self, player_id: str, scenario_id: str):
        super().__init__(
            event_type="SET_SCENARIO",
            data={
                "player_id": player_id,
                "scenario_id": scenario_id
            }
        )

class CreateRoomEvent(GameEvent):
    """创建房间事件"""
    def __init__(self, player_id: str, room_name: str):
        super().__init__(
            event_type="CREATE_ROOM",
            data={
                "player_id": player_id,
                "room_name": room_name
            }
        )

class JoinRoomEvent(GameEvent):
    """加入房间事件"""
    def __init__(self, player_id: str, player_name: str, room_id: str):
        super().__init__(
            event_type="JOIN_ROOM",
            data={
                "player_id": player_id,
                "player_name": player_name,
                "room_id": room_id
            }
        )

class PlayerLeftEvent(GameEvent):
    """玩家离开事件"""
    def __init__(self, player_id: str, player_name: str, room_id: str, room_empty: bool = False):
        super().__init__(
            event_type="PLAYER_LEFT",
            data={
                "player_id": player_id,
                "player_name": player_name,
                "room_id": room_id,
                "room_empty": room_empty
            }
        )

class ListRoomsEvent(GameEvent):
    """查询房间列表事件"""
    def __init__(self, player_id: str):
        super().__init__(
            event_type="LIST_ROOMS",
            data={
                "player_id": player_id
            }
        )

class SelectCharacterEvent(GameEvent):
    """选择角色事件"""
    def __init__(self, player_id: str, character_name: str):
        super().__init__(
            event_type="SELECT_CHARACTER",
            data={
                "player_id": player_id,
                "character_name": character_name
            }
        )

class MessageAdapter(ABC):
    """消息适配器抽象基类"""
    
    @abstractmethod
    async def start(self) -> None:
        """启动适配器"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止适配器"""
        pass
        
    @abstractmethod
    async def receive_message(self) -> Optional[GameEvent]:
        """接收外部消息并转换为游戏事件"""
        pass
        
    @abstractmethod
    async def send_message(self, player_id: str, content: str) -> None:
        """发送消息到指定玩家"""
        pass

class EventListener(ABC):
    """事件监听器接口"""
    
    @abstractmethod
    async def on_event(self, event: GameEvent) -> List[GameEvent]:
        """处理事件并返回响应事件列表"""
        pass

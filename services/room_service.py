import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus
from core.controllers.room_controller import RoomController
from core.controllers.character_controller import CharacterController
from services.game_state_service import GameStateService
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, PlayerLeftEvent
from core.events import EventBus

logger = logging.getLogger(__name__)

class RoomService:
    """房间服务，协调房间相关的业务逻辑"""
    
    def __init__(self, game_state_service: GameStateService, event_bus: Optional[EventBus] = None):
        """初始化房间服务
        
        Args:
            game_state_service: GameStateService - 游戏状态服务
            event_bus: Optional[EventBus] - 事件总线
        """
        self.game_state_service = game_state_service
        self.event_bus = event_bus
    
    async def create_room(self, name: str, host_id: Optional[str] = None) -> Tuple[RoomController, List[Dict[str, str]]]:
        """创建新房间
        
        Args:
            name: str - 房间名称
            host_id: Optional[str] - 房主ID
            
        Returns:
            Tuple[RoomController, List[Dict[str, str]]]: (房间控制器, 通知消息列表)
        """
        # 创建房间控制器
        room_controller = RoomController.create_room(name, host_id)
        
        # 注册房间到游戏实例
        self.game_state_service.register_room(room_controller.room.id, room_controller.room)
        
        # 生成通知消息
        messages = []
        
        # 如果有房主，通知房主
        if host_id:
            messages.append({"recipient": host_id, "content": f"成功创建房间: {name} (ID: {room_controller.room.id})"})
            
        logger.info(f"创建新房间: {name} (ID: {room_controller.room.id})")
        return room_controller, messages
    
    async def add_player_to_room(self, room_controller: RoomController, player_id: str, player_name: str) -> Tuple[Player, List[Dict[str, str]]]:
        """添加玩家到房间
        
        Args:
            room_controller: RoomController - 房间控制器
            player_id: str - 玩家ID
            player_name: str - 玩家名称
            
        Returns:
            Tuple[Player, List[Dict[str, str]]]: (添加的玩家, 通知消息列表)
        """
        # 使用RoomController添加玩家
        player = room_controller.add_player(player_id, player_name)
        
        # 更新玩家-房间映射
        self.game_state_service.update_player_room_mapping(player_id, room_controller.room.id)
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的其他玩家
        join_message = f"玩家 {player_name} 加入了房间"
        room_messages = self.broadcast_to_room(room_controller, join_message, [player_id])
        messages.extend(room_messages)
        
        # 通知新加入的玩家
        welcome_message = f"欢迎加入房间 {room_controller.room.name}"
        messages.append({"recipient": player_id, "content": welcome_message})
        
        # 发布玩家加入事件
        if self.event_bus:
            event = PlayerJoinedEvent(
                player_id=player_id,
                player_name=player_name,
                room_id=room_controller.room.id
            )
            await self.event_bus.publish(event)
            
        logger.info(f"玩家 {player_name} (ID: {player_id}) 加入房间 {room_controller.room.name} (ID: {room_controller.room.id})")
        return player, messages
    
    async def remove_player_from_room(self, room_controller: RoomController, player_id: str) -> Tuple[bool, List[Dict[str, str]]]:
        """将玩家从房间中移除
        
        Args:
            room_controller: RoomController - 房间控制器
            player_id: str - 玩家ID
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功移除, 通知消息列表)
        """
        # 获取玩家信息，用于后续通知
        player = room_controller.get_player_by_id(player_id)
        if not player:
            return False, []
            
        player_name = player.name
        
        # 使用RoomController移除玩家
        removed_player = room_controller.remove_player(player_id)
        
        if not removed_player:
            return False, []
            
        # 更新玩家-房间映射
        self.game_state_service.update_player_room_mapping(player_id, None)
        
        # 如果玩家有角色，更新玩家-角色映射
        if removed_player.character_id:
            self.game_state_service.update_player_character_mapping(player_id, None)
            
        # 生成通知消息
        messages = []
        
        # 通知房间中的其他玩家
        leave_message = f"玩家 {player_name} 离开了房间"
        room_messages = self.broadcast_to_room(room_controller, leave_message)
        messages.extend(room_messages)
        
        # 检查房间是否为空
        if not room_controller.room.players:
            # 房间为空，可以关闭
            self.game_state_service.unregister_room(room_controller.room.id)
            logger.info(f"房间已空，关闭房间: {room_controller.room.name} (ID: {room_controller.room.id})")
            
        # 发布玩家离开事件
        if self.event_bus:
            event = PlayerLeftEvent(
                player_id=player_id,
                player_name=player_name,
                room_id=room_controller.room.id,
                room_empty=len(room_controller.room.players) == 0
            )
            await self.event_bus.publish(event)
            
        logger.info(f"玩家 {player_name} (ID: {player_id}) 离开房间 {room_controller.room.name} (ID: {room_controller.room.id})")
        return True, messages
    
    def broadcast_to_room(self, room_controller: RoomController, message: str, exclude_players: List[str] = None) -> List[Dict[str, str]]:
        """向房间中所有玩家广播消息
        
        Args:
            room_controller: RoomController - 房间控制器
            message: str - 要广播的消息内容
            exclude_players: List[str] - 要排除的玩家ID列表
            
        Returns:
            List[Dict[str, str]]: 消息列表，每个消息包含recipient和content
        """
        exclude_players = exclude_players or []
        messages = []
        
        for player in room_controller.list_players():
            if player.id not in exclude_players:
                messages.append({"recipient": player.id, "content": message})
                
        return messages
    
    async def set_player_ready(self, room_controller: RoomController, player_id: str, is_ready: bool = True) -> Tuple[bool, List[Dict[str, str]]]:
        """设置玩家准备状态
        
        Args:
            room_controller: RoomController - 房间控制器
            player_id: str - 玩家ID
            is_ready: bool - 是否准备
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否设置成功, 通知消息列表)
        """
        # 使用RoomController设置玩家准备状态
        success = room_controller.set_player_ready(player_id, is_ready)
        
        if not success:
            return False, []
            
        # 获取玩家名称
        player = room_controller.get_player_by_id(player_id)
        if not player:
            return False, []
            
        player_name = player.name
        
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        status_message = f"玩家 {player_name} {'已准备' if is_ready else '取消准备'}"
        room_messages = self.broadcast_to_room(room_controller, status_message)
        messages.extend(room_messages)
        
        logger.info(f"玩家 {player_name} (ID: {player_id}) {'准备完毕' if is_ready else '取消准备'}")
        return True, messages
    
    async def kick_player(self, room_controller: RoomController, host_id: str, player_id: str) -> Tuple[bool, List[Dict[str, str]]]:
        """房主踢出玩家
        
        Args:
            room_controller: RoomController - 房间控制器
            host_id: str - 房主ID
            player_id: str - 要踢出的玩家ID
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功踢出, 通知消息列表)
        """
        # 验证操作者是否为房主
        host = room_controller.get_host()
        if not host or host.id != host_id:
            return False, [{"recipient": host_id, "content": "只有房主可以踢出玩家"}]
            
        # 获取玩家信息，用于后续通知
        player = room_controller.get_player_by_id(player_id)
        if not player:
            return False, [{"recipient": host_id, "content": "找不到要踢出的玩家"}]
            
        player_name = player.name
        
        # 使用RoomController踢出玩家
        kicked_player = room_controller.kick_player(player_id)
        
        if not kicked_player:
            return False, [{"recipient": host_id, "content": "踢出玩家失败"}]
            
        # 更新玩家-房间映射
        self.game_state_service.update_player_room_mapping(player_id, None)
        
        # 如果玩家有角色，更新玩家-角色映射
        if kicked_player.character_id:
            self.game_state_service.update_player_character_mapping(player_id, None)
            
        # 生成通知消息
        messages = []
        
        # 通知房间中的其他玩家
        kick_message = f"玩家 {player_name} 被房主踢出了房间"
        room_messages = self.broadcast_to_room(room_controller, kick_message)
        messages.extend(room_messages)
        
        # 通知被踢出的玩家
        messages.append({"recipient": player_id, "content": "你被房主踢出了房间"})
        
        # 发布玩家离开事件
        if self.event_bus:
            event = PlayerLeftEvent(
                player_id=player_id,
                player_name=player_name,
                room_id=room_controller.room.id,
                room_empty=False
            )
            await self.event_bus.publish(event)
            
        logger.info(f"玩家 {player_name} (ID: {player_id}) 被房主踢出房间 {room_controller.room.name} (ID: {room_controller.room.id})")
        return True, messages
    
    async def set_player_character(self, room_controller: RoomController, player_id: str, character_id: str) -> Tuple[bool, List[Dict[str, str]]]:
        """设置玩家的角色
        
        Args:
            room_controller: RoomController - 房间控制器
            player_id: str - 玩家ID
            character_id: str - 角色ID
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否设置成功, 通知消息列表)
        """
        # 使用RoomController设置玩家角色
        success = room_controller.set_player_character(player_id, character_id)
        
        if not success:
            return False, []
            
        # 更新玩家-角色映射
        self.game_state_service.update_player_character_mapping(player_id, character_id)
        
        # 获取玩家和角色信息，用于通知
        player = room_controller.get_player_by_id(player_id)
        if not player:
            return False, []
            
        player_name = player.name
        
        # 获取角色信息
        character = self.game_state_service.get_character_by_player_id(player_id)
        character_name = character.name if character else "未知角色"
        
        # 生成通知消息
        messages = []
        
        # 通知玩家
        messages.append({"recipient": player_id, "content": f"你选择了角色: {character_name}"})
        
        # 通知房间中的其他玩家
        select_message = f"玩家 {player_name} 选择了角色: {character_name}"
        room_messages = self.broadcast_to_room(room_controller, select_message, [player_id])
        messages.extend(room_messages)
        
        logger.info(f"玩家 {player_name} (ID: {player_id}) 选择了角色 {character_name} (ID: {character_id})")
        return True, messages
    
    async def get_room_controller(self, room_id: str) -> Optional[RoomController]:
        """获取房间控制器
        
        Args:
            room_id: str - 房间ID
            
        Returns:
            Optional[RoomController] - 房间控制器，如果不存在则返回None
        """
        room = self.game_state_service.get_room(room_id)
        if not room:
            return None
            
        return RoomController(room)
    
    async def get_player_room_controller(self, player_id: str) -> Optional[RoomController]:
        """获取玩家所在的房间控制器
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[RoomController] - 房间控制器，如果不存在则返回None
        """
        room = self.game_state_service.get_player_room(player_id)
        if not room:
            return None
            
        return RoomController(room)
    
    async def list_rooms(self) -> List[Dict[str, Any]]:
        """获取所有房间信息
        
        Returns:
            List[Dict[str, Any]] - 房间信息列表
        """
        rooms = self.game_state_service.list_rooms()
        room_info_list = []
        
        for room in rooms:
            room_controller = RoomController(room)
            room_info = room_controller.dump_state()
            room_info_list.append(room_info)
            
        return room_info_list

import logging
from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus
from core.controllers.room_controller import RoomController
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, PlayerLeftEvent
from core.events import EventBus

logger = logging.getLogger(__name__)

class RoomService:
    """房间服务，处理房间相关的业务逻辑"""
    
    def __init__(self, event_bus: EventBus = None):
        """初始化房间服务
        
        Args:
            event_bus: 事件总线，用于发布事件和消息
        """
        self.event_bus = event_bus
    
    async def create_room(self, name: str, host_id: str = None, game_instance=None) -> Tuple[Room, RoomController]:
        """创建新房间
        
        Args:
            name: 房间名称
            host_id: 房主ID（可选）
            game_instance: 游戏实例
            
        Returns:
            Tuple[Room, RoomController]: 创建的房间和房间控制器
        """
        room_id = str(uuid.uuid4())
        new_room = Room(id=room_id, name=name, host_id=host_id)
        
        # 创建房间控制器
        room_controller = RoomController(new_room, game_instance)
        
        # 房间创建完成
            
        logger.info(f"创建新房间: {name} (ID: {room_id})")
        return new_room, room_controller
    
    async def add_player_to_room(self, room_controller: RoomController, player_id: str, player_name: str) -> Tuple[Player, List[Dict[str, str]]]:
        """添加玩家到房间
        
        Args:
            room_controller: 房间控制器
            player_id: 玩家ID
            player_name: 玩家名称
            
        Returns:
            Tuple[Player, List[Dict[str, str]]]: 添加的玩家和通知消息列表
        """
        # 使用RoomController添加玩家
        player = room_controller.add_player(player_id, player_name)
        
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
    
    async def remove_player_from_room(self, room_controller: RoomController, player_id: str) -> Tuple[bool, Optional[PlayerLeftEvent], List[Dict[str, str]]]:
        """将玩家从房间中移除
        
        Args:
            room_controller: 房间控制器
            player_id: 玩家ID
            
        Returns:
            Tuple[bool, Optional[PlayerLeftEvent], List[Dict[str, str]]]: (是否成功移除, 玩家离开事件, 通知消息列表)
        """
        # 使用RoomController移除玩家
        success, event = room_controller.remove_player(player_id)
        
        if not success:
            return False, None, []
            
        # 生成通知消息
        messages = []
        
        # 通知房间中的其他玩家
        if event:
            leave_message = f"玩家 {event.player_name} 离开了房间"
            room_messages = self.broadcast_to_room(room_controller, leave_message)
            messages.extend(room_messages)
            
        # 发布玩家离开事件
        if self.event_bus and event:
            await self.event_bus.publish(event)
            
        logger.info(f"玩家 {event.player_name if event else player_id} 离开房间 {room_controller.room.name} (ID: {room_controller.room.id})")
        return True, event, messages
    
    def broadcast_to_room(self, room_controller: RoomController, message: str, exclude_players: List[str] = None) -> List[Dict[str, str]]:
        """向房间中所有玩家广播消息
        
        Args:
            room_controller: 房间控制器
            message: 要广播的消息内容
            exclude_players: 要排除的玩家ID列表
            
        Returns:
            List[Dict[str, str]]: 消息列表，每个消息包含recipient和content
        """
        exclude_players = exclude_players or []
        messages = []
        
        for player in room_controller.room.players:
            if player.id not in exclude_players:
                messages.append({"recipient": player.id, "content": message})
                
        return messages
    
    async def set_player_ready(self, room_controller: RoomController, player_id: str, is_ready: bool = True) -> Tuple[bool, List[Dict[str, str]]]:
        """设置玩家准备状态
        
        Args:
            room_controller: 房间控制器
            player_id: 玩家ID
            is_ready: 是否准备
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否设置成功, 通知消息列表)
        """
        # 使用RoomController设置玩家准备状态
        success = room_controller.set_player_ready(player_id, is_ready)
        
        if not success:
            return False, []
            
        # 获取玩家名称
        player_name = None
        for player in room_controller.room.players:
            if player.id == player_id:
                player_name = player.name
                break
                
        # 生成通知消息
        messages = []
        
        # 通知房间中的所有玩家
        status_message = f"玩家 {player_name} {'已准备' if is_ready else '取消准备'}"
        room_messages = self.broadcast_to_room(room_controller, status_message)
        messages.extend(room_messages)
        
        # 玩家准备状态已更新
            
        logger.info(f"玩家 {player_name} (ID: {player_id}) {'准备完毕' if is_ready else '取消准备'}")
        return True, messages
    
    async def kick_player(self, room_controller: RoomController, host_id: str, player_id: str) -> Tuple[bool, List[Dict[str, str]]]:
        """房主踢出玩家
        
        Args:
            room_controller: 房间控制器
            host_id: 房主ID
            player_id: 要踢出的玩家ID
            
        Returns:
            Tuple[bool, List[Dict[str, str]]]: (是否成功踢出, 通知消息列表)
        """
        # 验证操作者是否为房主
        host = room_controller.get_host()
        if not host or host.id != host_id:
            return False, [{"recipient": host_id, "content": "只有房主可以踢出玩家"}]
            
        # 使用RoomController踢出玩家
        success, event = room_controller.kick_player(player_id)
        
        if not success:
            return False, [{"recipient": host_id, "content": "踢出玩家失败"}]
            
        # 生成通知消息
        messages = []
        
        # 通知房间中的其他玩家
        if event:
            kick_message = f"玩家 {event.player_name} 被房主踢出了房间"
            room_messages = self.broadcast_to_room(room_controller, kick_message)
            messages.extend(room_messages)
            
            # 通知被踢出的玩家
            messages.append({"recipient": player_id, "content": "你被房主踢出了房间"})
            
        # 发布玩家离开事件
        if self.event_bus and event:
            await self.event_bus.publish(event)
            
        logger.info(f"玩家 {event.player_name if event else player_id} 被房主踢出房间 {room_controller.room.name} (ID: {room_controller.room.id})")
        return True, messages
    
    async def select_character(self, room_controller: RoomController, player_id: str, character_name: str) -> Tuple[bool, str, List[Dict[str, str]]]:
        """玩家选择角色
        
        Args:
            room_controller: 房间控制器
            player_id: 玩家ID
            character_name: 角色名称
            
        Returns:
            Tuple[bool, str, List[Dict[str, str]]]: (是否选择成功, 消息, 通知消息列表)
        """
        # 使用RoomController选择角色
        success, message = room_controller.select_character(player_id, character_name)
        
        # 生成通知消息
        messages = []
        
        # 通知玩家选择结果
        messages.append({"recipient": player_id, "content": message})
        
        if success:
            # 获取玩家名称
            player_name = None
            for player in room_controller.room.players:
                if player.id == player_id:
                    player_name = player.name
                    break
                    
            # 通知房间中的其他玩家
            select_message = f"玩家 {player_name} 选择了角色 {character_name}"
            room_messages = self.broadcast_to_room(room_controller, select_message, [player_id])
            messages.extend(room_messages)
                
            logger.info(f"玩家 {player_name} (ID: {player_id}) 选择了角色 {character_name}")
            
        return success, message, messages
    
    async def set_scenario(self, room_controller: RoomController, scenario_id: str) -> Tuple[bool, Optional[str], List[Dict[str, str]]]:
        """设置当前游戏使用的剧本
        
        Args:
            room_controller: 房间控制器
            scenario_id: 剧本ID
            
        Returns:
            Tuple[bool, Optional[str], List[Dict[str, str]]]: (是否设置成功, 错误消息, 通知消息列表)
        """
        # 使用RoomController设置剧本
        success, error_msg = room_controller.set_scenario(scenario_id)
        
        # 生成通知消息
        messages = []
        
        if success:
            # 通知房间中的所有玩家
            scenario_message = f"房间剧本已设置为: {scenario_id}"
            room_messages = self.broadcast_to_room(room_controller, scenario_message)
            messages.extend(room_messages)
                
            logger.info(f"为房间 {room_controller.room.name} (ID: {room_controller.room.id}) 设置剧本: {scenario_id}")
        else:
            logger.warning(f"设置剧本失败: {error_msg}")
            
        return success, error_msg, messages

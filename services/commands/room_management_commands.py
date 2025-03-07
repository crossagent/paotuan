import logging
from typing import List, Dict, Any, Optional, Union

from adapters.base import GameEvent, CreateRoomEvent, JoinRoomEvent, ListRoomsEvent
from services.commands.base import GameCommand
from services.room_service import RoomService

logger = logging.getLogger(__name__)

class CreateRoomCommand(GameCommand):
    """处理创建房间事件的命令"""
    
    async def execute(self, event: CreateRoomEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: CreateRoomEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        room_name = event.data["room_name"]
        
        logger.info(f"处理创建房间事件: 玩家ID={player_id}, 房间名称={room_name}")
        
        # 获取房间服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 创建新房间
        room_controller = await room_service.create_room(room_name)
        
        # 返回创建成功消息
        return [{
            "recipient": player_id, 
            "content": f"成功创建房间: {room_name} (ID: {room_controller.room.id})\n使用 /加入房间 {room_controller.room.id} 加入此房间"
        }]


class JoinRoomCommand(GameCommand):
    """处理加入房间事件的命令"""
    
    async def execute(self, event: JoinRoomEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: JoinRoomEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        room_id = event.data["room_id"]
        
        logger.info(f"处理加入房间事件: 玩家={player_name}({player_id}), 房间ID={room_id}")
        
        # 获取房间服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 获取房间控制器
        room_controller = await room_service.get_room_controller(room_id)
        if not room_controller:
            return [{"recipient": player_id, "content": f"房间不存在: {room_id}"}]
        
        # 添加玩家
        success, message = await room_service.add_player_to_room(room_controller, player_id, player_name)
        if not success:
            return [{"recipient": player_id, "content": message}]
        
        # 返回加入成功消息
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room_controller.room.name} (ID: {room_controller.room.id})"}]


class ListRoomsCommand(GameCommand):
    """处理查询房间列表事件的命令"""
    
    async def execute(self, event: ListRoomsEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: ListRoomsEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        
        logger.info(f"处理查询房间列表事件: 玩家ID={player_id}")
        
        # 获取房间服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 获取所有房间
        room_controllers = await room_service.list_rooms()
        
        if not room_controllers:
            return [{"recipient": player_id, "content": "当前没有可用的房间，请使用 /创建房间 [房间名] 创建新房间"}]
        
        # 构建房间列表消息
        rooms_msg = "可用房间列表:\n"
        for room_controller in room_controllers:
            room = room_controller.room
            
            # 获取房间状态 - 直接从房间控制器获取
            status = room.status if hasattr(room, 'status') else "未知"
            player_count = len(room_controller.get_players())
            
            rooms_msg += f"- {room.name} (ID: {room.id})\n"
            rooms_msg += f"  状态: {status}, 玩家数: {player_count}\n"
        
        rooms_msg += "\n使用 /加入房间 [房间ID] 加入房间"
        
        # 返回房间列表消息
        return [{"recipient": player_id, "content": rooms_msg}]


class LeaveRoomCommand(GameCommand):
    """处理玩家离开房间事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        try:
            player_id = event.data.get("player_id")
            player_name = event.data.get("player_name")
            room_id = event.data.get("room_id")
            room_empty = event.data.get("room_empty", False)
            
            logger.info(f"玩家离开: {player_name} (ID: {player_id}), 房间: {room_id}, 房间是否为空: {room_empty}")
            
            # 获取房间服务
            room_service = self.service_provider.get_service(RoomService)
            
            # 如果房间为空，自动关闭房间
            if room_empty and room_id:
                logger.info(f"自动关闭空房间: {room_id}")
                await room_service.close_room(room_id)
                
                # 通知玩家房间已关闭
                return [{"recipient": player_id, "content": f"房间已自动关闭: {room_id}"}]
                
            return []
        except Exception as e:
            logger.exception(f"处理玩家离开事件失败: {str(e)}")
            return []

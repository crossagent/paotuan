import logging
from typing import List, Dict, Any, Optional, Union

from adapters.base import GameEvent, CreateRoomEvent, JoinRoomEvent, ListRoomsEvent, SetPlayerReadyEvent, KickPlayerEvent
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
        default_scenario_id = event.data.get("scenario_id")  # 可选的默认剧本ID
        
        logger.info(f"处理创建房间事件: 玩家ID={player_id}, 房间名称={room_name}, 默认剧本ID={default_scenario_id or '无'}")
        
        # 获取房间服务
        room_service:RoomService = self.service_provider.get_service(RoomService)
        
        # 创建新房间
        room_context, msgs = await room_service.create_room(room_name, player_id, default_scenario_id)
        
        # 拼接消息列表中的所有消息内容（假设每个字典都有 "content" 字段）
        extra_messages = " ".join(msg.get("content", "") for msg in msgs)

        # 返回创建成功消息，并将额外消息也包含进去
        return [{
            "recipient": player_id, 
            "content": (
                f"成功创建房间: {room_name} (ID: {room_context.room.id})\n"
                f"使用 /加入房间 {room_context.room.id} 加入此房间\n"
                f"附加信息: {extra_messages}"
            )
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
        room_context = await room_service.get_room_context(room_id)
        if not room_context:
            return [{"recipient": player_id, "content": f"房间不存在: {room_id}"}]
        
        # 添加玩家
        success, message = await room_service.add_player_to_room(room_context, player_id, player_name)
        if not success:
            return [{"recipient": player_id, "content": message}]
        
        # 返回加入成功消息
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room_context.room.name} (ID: {room_context.room.id})"}]


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
        room_contexts = await room_service.list_rooms()
        
        if not room_contexts:
            return [{"recipient": player_id, "content": "当前没有可用的房间，请使用 /创建房间 [房间名] 创建新房间"}]
        
        # 构建房间列表消息
        rooms_msg = "可用房间列表:\n"
        for room_context in room_contexts:
            room = room_context.room
            
            # 获取房间状态
            player_count = len(room_context.list_players())
            
            rooms_msg += f"- {room.name} (ID: {room.id})\n"
            rooms_msg += f"  玩家数: {player_count}\n"
        
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
            
            # 获取房间控制器
            room_context = await room_service.get_room_context(room_id)

            # 从房间中移除玩家
            result, msg = await room_service.remove_player_from_room(room_context, player_id)
                
            # 如果房间为空，通知所有人房间已关闭；否则只给离开的玩家和房间内其他玩家发送不同消息
            if room_empty:
                return [{
                    "recipient": "room", 
                    "content": f"房间 {room_id} 已空，已关闭。"
                }]
            else:
                return [
                    {
                        "recipient": player_id, 
                        "content": f"你已成功离开房间 {room_id}。"
                    },
                    {
                        "recipient": "room",
                        "content": f"玩家 {player_name} 已离开房间。"
                    }
                ]
        except Exception as e:
            logger.exception(f"处理玩家离开事件失败: {str(e)}")
            return []


class SetPlayerReadyCommand(GameCommand):
    """处理设置玩家准备状态事件的命令"""
    
    async def execute(self, event: SetPlayerReadyEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: SetPlayerReadyEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        room_id = event.data["room_id"]
        is_ready = event.data["is_ready"]
        
        logger.info(f"处理设置玩家准备状态事件: 玩家ID={player_id}, 房间ID={room_id}, 准备状态={is_ready}")
        
        # 获取房间服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 获取房间控制器
        room_context = await room_service.get_room_context(room_id)
        if not room_context:
            return [{"recipient": player_id, "content": f"房间不存在: {room_id}"}]
        
        # 设置玩家准备状态
        success, message = await room_service.set_player_ready(room_context, player_id, is_ready)
        if not success:
            return [{"recipient": player_id, "content": message}]
        
        # 检查是否所有玩家都已准备
        all_ready = room_context.are_all_players_ready()
        
        # 返回设置成功消息
        return [{
            "recipient": player_id, 
            "content": f"你已{'准备完毕' if is_ready else '取消准备'}" + 
                      (f"，所有玩家已准备完毕，可以开始游戏" if all_ready else "")
        }]


class KickPlayerCommand(GameCommand):
    """处理踢出玩家事件的命令"""
    
    async def execute(self, event: KickPlayerEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: KickPlayerEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        host_id = event.data["host_id"]
        player_id = event.data["player_id"]
        room_id = event.data["room_id"]
        
        logger.info(f"处理踢出玩家事件: 房主ID={host_id}, 玩家ID={player_id}, 房间ID={room_id}")
        
        # 获取房间服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 获取房间控制器
        room_context = await room_service.get_room_context(room_id)
        if not room_context:
            return [{"recipient": host_id, "content": f"房间不存在: {room_id}"}]
        
        # 踢出玩家
        success, message = await room_service.kick_player(room_context, host_id, player_id)
        if not success:
            return [{"recipient": host_id, "content": message}]
        
        # 返回踢出成功消息
        return [
            {"recipient": host_id, "content": f"已将玩家踢出房间"},
            {"recipient": player_id, "content": f"你已被房主踢出房间: {room_context.room.name}"}
        ]

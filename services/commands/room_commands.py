import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import Room, Match, Player, GameStatus
from core.room import RoomManager
from adapters.base import GameEvent, CreateRoomEvent, JoinRoomEvent, ListRoomsEvent
from services.commands.base import GameCommand

logger = logging.getLogger(__name__)

class CreateRoomCommand(GameCommand):
    """处理创建房间事件的命令"""
    
    async def execute(self, event: CreateRoomEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        room_name = event.data["room_name"]
        
        logger.info(f"处理创建房间事件: 玩家ID={player_id}, 房间名称={room_name}")
        
        # 创建新房间
        room = self.game_instance.create_room(room_name)
        
        # 返回创建成功消息
        return [{
            "recipient": player_id, 
            "content": f"成功创建房间: {room_name} (ID: {room.id})\n使用 /加入房间 {room.id} 加入此房间"
        }]


class JoinRoomCommand(GameCommand):
    """处理加入房间事件的命令"""
    
    async def execute(self, event: JoinRoomEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        room_id = event.data["room_id"]
        
        logger.info(f"处理加入房间事件: 玩家={player_name}({player_id}), 房间ID={room_id}")
        
        # 获取房间
        room = self._get_room_by_id(room_id)
        if not room:
            return [{"recipient": player_id, "content": f"房间不存在: {room_id}"}]
        
        # 创建房间管理器
        room_manager = RoomManager(room, self.game_instance)
        
        # 添加玩家
        player = room_manager.add_player(player_id, player_name)
        
        # 返回加入成功消息
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room.name} (ID: {room.id})"}]


class ListRoomsCommand(GameCommand):
    """处理查询房间列表事件的命令"""
    
    async def execute(self, event: ListRoomsEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        
        logger.info(f"处理查询房间列表事件: 玩家ID={player_id}")
        
        # 获取所有房间
        rooms = self.game_instance.list_rooms()
        
        if not rooms:
            return [{"recipient": player_id, "content": "当前没有可用的房间，请使用 /创建房间 [房间名] 创建新房间"}]
        
        # 构建房间列表消息
        rooms_msg = "可用房间列表:\n"
        for room in rooms:
            # 获取房间状态
            current_match = None
            for match in room.matches:
                if match.id == room.current_match_id:
                    current_match = match
                    break
                    
            status = "等待中"
            if current_match:
                if current_match.status == GameStatus.RUNNING:
                    status = "游戏中"
                elif current_match.status == GameStatus.PAUSED:
                    status = "已暂停"
                elif current_match.status == GameStatus.FINISHED:
                    status = "已结束"
            
            rooms_msg += f"- {room.name} (ID: {room.id})\n"
            rooms_msg += f"  状态: {status}, 玩家数: {len(room.players)}\n"
        
        rooms_msg += "\n使用 /加入房间 [房间ID] 加入房间"
        
        # 返回房间列表消息
        return [{"recipient": player_id, "content": rooms_msg}]

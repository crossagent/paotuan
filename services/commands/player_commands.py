import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import Room, Match, Player, Character, TurnType, TurnStatus, GameStatus, DiceTurn
from core.room import RoomManager
from core.turn import TurnManager
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent, SelectCharacterEvent
from services.commands.base import GameCommand

logger = logging.getLogger(__name__)

class PlayerJoinedCommand(GameCommand):
    """处理玩家加入事件的命令"""
    
    async def execute(self, event: PlayerJoinedEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理玩家加入事件: 玩家={player_name}({player_id})")
        
        # 获取所有房间
        rooms = self.game_instance.list_rooms()
        
        # 如果没有房间，创建一个默认房间
        if not rooms:
            room = self.game_instance.create_room("默认房间")
            room_manager = RoomManager(room, self.game_instance)
            player = room_manager.add_player(player_id, player_name)
            
            logger.info(f"创建默认房间并添加玩家: {player_name}({player_id}), 房间={room.name}")
            
            return [{"recipient": player_id, "content": f"已创建默认房间并加入: {room.name} (ID: {room.id})"}]
        
        # 如果有多个房间，返回房间列表让玩家选择
        if len(rooms) > 1:
            rooms_msg = "当前有多个房间可用，请选择一个加入:\n"
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
            
            rooms_msg += "\n使用 /加入房间 [房间ID] 加入指定房间"
            
            logger.info(f"向玩家发送房间列表: {player_name}({player_id})")
            
            return [{"recipient": player_id, "content": rooms_msg}]
        
        # 如果只有一个房间，直接加入
        room = rooms[0]
        room_manager = RoomManager(room, self.game_instance)
        player = room_manager.add_player(player_id, player_name)
        
        logger.info(f"玩家加入唯一房间: {player_name}({player_id}), 房间={room.name}")
        
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room.name} (ID: {room.id})"}]



class SelectCharacterCommand(GameCommand):
    """处理选择角色事件的命令"""
    
    async def execute(self, event: SelectCharacterEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        character_name = event.data["character_name"]
        
        logger.info(f"处理选择角色事件: 玩家ID={player_id}, 角色名称={character_name}")
        
        # 查找玩家所在的房间
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 选择角色
        success, message = room_manager.select_character(player_id, character_name)
        
        # 查找玩家名称
        player_name = "未知玩家"
        for p in player_room.players:
            if p.id == player_id:
                player_name = p.name
                break
        
        if success:
            # 通知所有玩家
            messages = []
            for p in player_room.players:
                if p.id != player_id:  # 不通知选择角色的玩家自己
                    messages.append({"recipient": p.id, "content": f"玩家 {player_name} 选择了角色: {character_name}"})
            
            # 通知选择角色的玩家
            messages.append({"recipient": player_id, "content": message})
            return messages
        else:
            # 选择失败，只通知选择角色的玩家
            return [{"recipient": player_id, "content": message}]


class PlayerLeftCommand(GameCommand):
    """处理玩家离开事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """处理玩家离开事件"""
        try:
            player_id = event.data.get("player_id")
            player_name = event.data.get("player_name")
            room_id = event.data.get("room_id")
            room_empty = event.data.get("room_empty", False)
            
            logger.info(f"玩家离开: {player_name} (ID: {player_id}), 房间: {room_id}, 房间是否为空: {room_empty}")
            
            # 如果房间为空，自动关闭房间
            if room_empty and room_id in self.game_instance.rooms:
                logger.info(f"自动关闭空房间: {room_id}")
                del self.game_instance.rooms[room_id]
                
                # 通知其他玩家房间已关闭
                return [{"recipient": player_id, "content": f"房间已自动关闭: {room_id}"}]
                
            return []
        except Exception as e:
            logger.exception(f"处理玩家离开事件失败: {str(e)}")
            return []

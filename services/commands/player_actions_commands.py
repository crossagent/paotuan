import logging
from typing import List, Dict, Any, Optional, Union

from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, SelectCharacterEvent
from services.commands.base import GameCommand
from services.room_service import RoomService
from services.match_service import MatchService
from services.turn_service import TurnService

logger = logging.getLogger(__name__)

class PlayerJoinedCommand(GameCommand):
    """处理玩家加入事件的命令"""
    
    async def execute(self, event: PlayerJoinedEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: PlayerJoinedEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理玩家加入事件: 玩家={player_name}({player_id})")
        
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 获取所有房间
        room_controllers = await room_service.list_rooms()
        
        # 如果没有房间，创建一个默认房间
        if not room_controllers:
            room_controller = await room_service.create_room("默认房间")
            success, message = await room_service.add_player_to_room(room_controller, player_id, player_name)
            
            logger.info(f"创建默认房间并添加玩家: {player_name}({player_id}), 房间={room_controller.room.name}")
            
            return [{"recipient": player_id, "content": f"已创建默认房间并加入: {room_controller.room.name} (ID: {room_controller.room.id})"}]
        
        # 如果有多个房间，返回房间列表让玩家选择
        if len(room_controllers) > 1:
            rooms_msg = "当前有多个房间可用，请选择一个加入:\n"
            for room_controller in room_controllers:
                room = room_controller.room
                
                # 获取房间状态 - 直接从房间控制器获取
                status = room.status if hasattr(room, 'status') else "未知"
                player_count = len(room_controller.get_players())
                
                rooms_msg += f"- {room.name} (ID: {room.id})\n"
                rooms_msg += f"  状态: {status}, 玩家数: {player_count}\n"
            
            rooms_msg += "\n使用 /加入房间 [房间ID] 加入指定房间"
            
            logger.info(f"向玩家发送房间列表: {player_name}({player_id})")
            
            return [{"recipient": player_id, "content": rooms_msg}]
        
        # 如果只有一个房间，直接加入
        room_controller = room_controllers[0]
        success, message = await room_service.add_player_to_room(room_controller, player_id, player_name)
        
        logger.info(f"玩家加入唯一房间: {player_name}({player_id}), 房间={room_controller.room.name}")
        
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room_controller.room.name} (ID: {room_controller.room.id})"}]


class SelectCharacterCommand(GameCommand):
    """处理选择角色事件的命令"""
    
    async def execute(self, event: SelectCharacterEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: SelectCharacterEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        character_name = event.data["character_name"]
        
        logger.info(f"处理选择角色事件: 玩家ID={player_id}, 角色名称={character_name}")
        
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        
        # 获取玩家所在房间的控制器
        room_controller = await room_service.get_player_room_controller(player_id)
        if not room_controller:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 获取游戏局控制器
        match_controller = await match_service.get_match_controller(room_controller)
        if not match_controller:
            return [{"recipient": player_id, "content": "当前没有游戏局，请先创建游戏局"}]
        
        # 选择角色
        success, message, notifications = await match_service.select_character(match_controller, room_controller, player_id, character_name)
        
        if not success:
            return [{"recipient": player_id, "content": message}]
        
        # 构建通知消息
        messages = []
        
        # 通知选择角色的玩家
        messages.append({"recipient": player_id, "content": message})
        
        # 通知其他玩家
        messages.extend(notifications)
        
        return messages


class CharacterActionCommand(GameCommand):
    """处理角色行动事件的命令"""
    
    async def execute(self, event: PlayerActionEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: PlayerActionEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        action = event.data["action"]
        
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        turn_service = self.service_provider.get_service(TurnService)
        
        # 获取玩家所在房间的控制器
        room_controller = await room_service.get_player_room_controller(player_id)
        if not room_controller:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 获取游戏局控制器
        match_controller = await match_service.get_match_controller(room_controller)
        if not match_controller:
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
            
        # 检查游戏局状态
        if not await match_service.is_match_running(match_controller):
            return [{"recipient": player_id, "content": f"当前游戏局未在运行中"}]
            
        # 获取当前回合控制器
        turn_controller = await turn_service.get_turn_context(match_controller)
        if not turn_controller:
            return [{"recipient": player_id, "content": "当前没有活动回合"}]
            
        # 检查是否是玩家回合
        if not await turn_service.is_player_turn(turn_controller):
            return []
        
        # 获取玩家角色控制器
        character_controller = await match_service.get_character_controller_by_player_id(match_controller, player_id)
        if not character_controller:
            return [{"recipient": player_id, "content": "找不到你的游戏角色，请尝试重新加入房间"}]
        
        # 处理玩家行动
        success, action_messages = await turn_service.process_player_action(
            player_id=player_id, 
            action=action, 
            turn_controller=turn_controller, 
            match_controller=match_controller,
            character_controller=character_controller
        )
        
        if not success:
            return action_messages
            
        # 检查回合是否完成
        if not await turn_service.is_turn_completed(turn_controller):
            return action_messages
            
        # 收集所有消息
        messages = action_messages.copy()
        
        # 转换到DM回合
        dm_turn_controller, transition_messages = await turn_service.transition_to_dm_turn(match_controller, room_controller)
        messages.extend(transition_messages)
        
        # 触发DM叙述事件
        dm_narration_event = await turn_service.create_dm_narration_event(room_controller.room.id)
        messages.append(dm_narration_event)
        
        return messages

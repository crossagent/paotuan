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
        room_id = event.data.get("room_id")
        
        logger.info(f"处理玩家加入事件: 玩家={player_name}({player_id}), 目标房间ID={room_id}")
        
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        
        # 必须指定房间ID
        if not room_id:
            logger.warning(f"玩家尝试加入房间但未指定房间ID: {player_name}({player_id})")
            return [{"recipient": player_id, "content": "请指定要加入的房间ID，使用 /加入房间 [房间ID]"}]
        
        # 尝试获取指定的房间
        room_context = await room_service.get_room_context(room_id)
        if not room_context:
            logger.warning(f"玩家尝试加入不存在的房间: {room_id}")
            return [{"recipient": player_id, "content": f"找不到ID为 {room_id} 的房间"}]
        
        # 加入指定的房间
        player, messages = await room_service.add_player_to_room(room_context, player_id, player_name)
        
        if player is None:
            # 加入房间失败（可能房间已满）
            error_message = messages[0]["content"] if messages else "加入指定房间失败"
            logger.warning(f"玩家加入指定房间失败: {error_message}")
            return [{"recipient": player_id, "content": error_message}]
        
        logger.info(f"玩家加入指定房间: {player_name}({player_id}), 房间={room_context.room.name}")
        
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room_context.room.name} (ID: {room_context.room.id})"}]


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
        room_context = await room_service.get_player_room_context(player_id)
        if not room_context:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 获取游戏局控制器
        match_context = await match_service.get_match_context(room_context)
        if not match_context:
            return [{"recipient": player_id, "content": "当前没有游戏局，请先创建游戏局"}]
        
        # 选择角色
        success, message, notifications = await match_service.select_character(match_context, room_context, player_id, character_name)
        
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
        room_context = await room_service.get_player_room_context(player_id)
        if not room_context:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 获取游戏局控制器
        match_context = await match_service.get_match_context(room_context)
        if not match_context:
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
            
        # 检查游戏局状态
        if not await match_service.is_match_running(match_context):
            return [{"recipient": player_id, "content": f"当前游戏局未在运行中"}]
            
        # 获取当前回合控制器
        turn_context = await turn_service.get_turn_context(match_context)
        if not turn_context:
            return [{"recipient": player_id, "content": "当前没有活动回合"}]
            
        # 检查是否是玩家回合
        if not await turn_service.is_player_turn(turn_context):
            return []
        
        # 获取玩家角色控制器
        character_context = await match_service.get_character_context_by_player_id(match_context, player_id)
        if not character_context:
            return [{"recipient": player_id, "content": "找不到你的游戏角色，请尝试重新加入房间"}]
        
        # 处理玩家行动
        success, action_messages = await turn_service.process_player_action(
            player_id=player_id, 
            action=action, 
            turn_context=turn_context, 
            match_context=match_context,
            character_context=character_context
        )
        
        if not success:
            return action_messages
            
        # 检查回合是否完成
        if not await turn_service.is_turn_completed(turn_context):
            return action_messages
            
        # 收集所有消息
        messages = action_messages.copy()
        
        # 转换到DM回合
        dm_turn_context, transition_messages = await turn_service.transition_to_dm_turn(match_context, room_context)
        messages.extend(transition_messages)
        
        # 触发DM叙述事件
        dm_narration_event = await turn_service.create_dm_narration_event(room_context.room.id)
        messages.append(dm_narration_event)
        
        return messages

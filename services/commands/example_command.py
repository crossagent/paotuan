import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import GameStatus, DMTurn, TurnType
from core.controllers.character_controller import CharacterController
from services.commands.base import GameCommand
from services.game_service import GameService
from services.room_service import RoomService
from services.match_service import MatchService
from services.turn_service import TurnService
from adapters.base import GameEvent

logger = logging.getLogger(__name__)

class StartGameCommand(GameCommand):
    """开始游戏命令示例"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data.get("player_id")
        room_id = event.data.get("room_id")
        
        # 获取游戏服务
        game_service = self.service_provider.get_service(GameService)
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        
        # 获取房间控制器
        room_controller = await room_service.get_room_controller(room_id)
        if not room_controller:
            return [{"recipient": player_id, "content": "找不到指定的房间"}]
        
        # 检查是否是房主
        host = room_controller.get_host()
        if not host or host.id != player_id:
            return [{"recipient": player_id, "content": "只有房主可以开始游戏"}]
        
        # 获取当前游戏局控制器
        match_controller = await match_service.get_match_controller(room_controller)
        if not match_controller:
            # 创建新游戏局
            match_controller, messages = await match_service.create_match(room_controller, "新的冒险")
            if not match_controller:
                return [{"recipient": player_id, "content": "创建游戏局失败"}]
            
            # 设置剧本
            scenario_id = event.data.get("scenario_id", "default")
            success, error_msg, scenario_messages = await match_service.set_scenario(match_controller, room_controller, scenario_id)
            if not success:
                return [{"recipient": player_id, "content": f"设置剧本失败: {error_msg}"}]
            
            messages.extend(scenario_messages)
        
        # 开始游戏
        success, start_messages = await match_service.start_match(match_controller, room_controller)
        if not success:
            return [{"recipient": player_id, "content": "开始游戏失败"}]
        
        # 返回所有通知消息
        return start_messages


class PlayerActionCommand(GameCommand):
    """玩家行动命令示例"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data.get("player_id")
        action = event.data.get("action")
        
        if not action:
            return [{"recipient": player_id, "content": "请输入行动内容"}]
        
        # 获取服务
        game_service = self.service_provider.get_service(GameService)
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        turn_service = self.service_provider.get_service(TurnService)
        
        # 获取玩家所在的房间
        room_controller = await room_service.get_player_room_controller(player_id)
        if not room_controller:
            return [{"recipient": player_id, "content": "你不在任何房间中"}]
        
        # 获取当前游戏局
        match_controller = await match_service.get_match_controller(room_controller)
        if not match_controller:
            return [{"recipient": player_id, "content": "当前没有游戏局"}]
        
        # 检查游戏是否在运行中
        if match_controller.match.status != GameStatus.RUNNING:
            return [{"recipient": player_id, "content": f"游戏未在运行中，当前状态: {match_controller.match.status}"}]
        
        # 获取当前回合
        turn_controller = await turn_service.get_turn_controller(match_controller)
        if not turn_controller:
            return [{"recipient": player_id, "content": "当前没有回合"}]
        
        # 获取玩家角色
        character = match_controller.get_character_by_player_id(player_id)
        character_controller = None
        if character:
            character_controller = CharacterController(character)
        
        # 处理玩家行动
        success, messages = await turn_service.process_player_action(
            player_id=player_id,
            action=action,
            turn_controller=turn_controller,
            match_controller=match_controller,
            character_controller=character_controller
        )
        
        if not success:
            return [{"recipient": player_id, "content": "处理行动失败"}]
        
        return messages


class DMNarrationCommand(GameCommand):
    """DM叙述命令示例"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data.get("player_id")
        narration = event.data.get("narration")
        active_players = event.data.get("active_players", [])
        
        if not narration:
            return [{"recipient": player_id, "content": "请输入叙述内容"}]
        
        # 获取服务
        game_service = self.service_provider.get_service(GameService)
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        turn_service = self.service_provider.get_service(TurnService)
        
        # 获取房主所在的房间
        room_controller = await room_service.get_player_room_controller(player_id)
        if not room_controller:
            return [{"recipient": player_id, "content": "你不在任何房间中"}]
        
        # 检查是否是房主
        host = room_controller.get_host()
        if not host or host.id != player_id:
            return [{"recipient": player_id, "content": "只有房主可以进行DM叙述"}]
        
        # 获取当前游戏局
        match_controller = await match_service.get_match_controller(room_controller)
        if not match_controller:
            return [{"recipient": player_id, "content": "当前没有游戏局"}]
        
        # 检查游戏是否在运行中
        if match_controller.match.status != GameStatus.RUNNING:
            return [{"recipient": player_id, "content": f"游戏未在运行中，当前状态: {match_controller.match.status}"}]
        
        # 获取或创建DM回合
        turn_controller = await turn_service.get_turn_controller(match_controller)
        if not turn_controller or not isinstance(turn_controller.turn, DMTurn):
            # 创建新的DM回合
            turn_controller, dm_messages = await turn_service.transition_to_dm_turn(match_controller, room_controller)
        
        # 设置DM叙述
        messages = await turn_service.set_dm_narration(turn_controller, narration, match_controller, room_controller)
        
        # 如果指定了激活玩家，转换到玩家回合
        if active_players:
            # 完成当前回合，创建新的玩家回合
            turn_controller.complete_turn(TurnType.PLAYER, active_players)
            
            # 创建新的玩家回合
            new_turn_controller, player_messages = await turn_service.transition_to_player_turn(
                match_controller=match_controller,
                room_controller=room_controller,
                active_players=active_players
            )
            
            messages.extend(player_messages)
        
        return messages

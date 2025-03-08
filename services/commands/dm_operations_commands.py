import logging
from typing import List, Dict, Any, Optional, Union

from adapters.base import GameEvent, DMNarrationEvent
from services.commands.base import GameCommand
from services.room_service import RoomService
from services.match_service import MatchService
from services.turn_service import TurnService
from services.narration_service import NarrationService

logger = logging.getLogger(__name__)

class DMNarrationCommand(GameCommand):
    """处理DM叙述事件的命令"""
    
    async def execute(self, event: DMNarrationEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: DMNarrationEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        turn_service = self.service_provider.get_service(TurnService)
        narration_service = self.service_provider.get_service(NarrationService)
        
        # 获取room_id
        room_id = event.data.get("room_id")
        
        # 如果提供了room_id，直接获取对应的房间
        if not room_id:
            logger.warning("DMNarrationEvent缺少room_id参数")
            return []
            
        # 获取房间控制器
        room_controller = await room_service.get_room_controller(room_id)
        if not room_controller:
            logger.warning(f"找不到房间: ID={room_id}")
            return []
        
        # 获取游戏局控制器
        match_controller = await match_service.get_match_controller(room_controller)
        if not match_controller:
            logger.warning("当前没有进行中的游戏局")
            return []
            
        # 检查游戏局状态
        if not await match_service.is_match_running(match_controller):
            logger.warning(f"游戏局未在运行中: ID={match_controller.match.id}")
            return []
            
        # 获取回合控制器
        turn_controller = await turn_service.get_turn_context(match_controller)
        if not turn_controller:
            logger.warning("当前没有活动回合")
            return []
        
        # 检查是否是DM回合
        if not await turn_service.is_dm_turn(turn_controller):
            logger.warning("当前不是DM回合")
            return []
        
        # 准备AI上下文
        players = room_controller.get_players()
        player_ids = [p.id for p in players]
        
        # 获取上下文信息
        context = await narration_service.prepare_context(match_controller, turn_controller, players)
        
        # 加载剧本（如果有）
        scenario = await narration_service.load_scenario(match_controller)
        
        # 调用AI服务生成叙述
        response = await narration_service.generate_narration(context, scenario)
        
        # 处理AI响应
        messages = []
        
        # 处理位置、物品和剧情更新
        update_messages = await narration_service.process_ai_response(response, room_controller, scenario)
        
        # 检查是否有系统通知消息
        system_notifications = []
        regular_messages = []
        
        for msg in update_messages:
            # 分离系统通知和普通消息
            if isinstance(msg, dict) and msg.get("type") == "system_notification":
                system_notifications.append(msg)
            else:
                regular_messages.append(msg)
        
        # 处理系统通知
        for notification in system_notifications:
            if notification.get("action") == "finish_match":
                # 结束游戏局
                result = notification.get("result", "AI决定结束游戏")
                await match_service.end_match(match_controller, result)
                logger.info(f"游戏局已结束：ID={match_controller.match.id}, 结果={result}")
        
        # 将普通消息添加到返回列表
        messages.extend(regular_messages)
        
        # 处理回合转换和通知玩家
        turn_messages = await turn_service.handle_turn_transition(response, turn_controller, match_controller, player_ids)
        messages.extend(turn_messages)
        
        return messages

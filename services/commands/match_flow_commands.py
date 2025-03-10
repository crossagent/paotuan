import logging
from typing import List, Dict, Any, Optional, Union

from adapters.base import GameEvent, SetScenarioEvent, DMNarrationEvent
from services.commands.base import GameCommand
from services.room_service import RoomService
from services.match_service import MatchService
from services.turn_service import TurnService
from utils.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)

class StartMatchCommand(GameCommand):
    """处理开始游戏局(match)事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理开始游戏局事件: 发起者={player_name}({player_id})")
        
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        
        # 获取玩家所在房间的控制器
        room_context = await room_service.get_player_room_context(player_id)
        if not room_context:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 检查是否为房主
        if room_context.room.host_id != player_id:
            return [{"recipient": player_id, "content": "只有房主才能开始游戏"}]
        
        # 检查房间中是否有玩家
        if not room_context.list_players():
            logger.warning(f"开始游戏局失败: 房间中没有玩家")
            return [{"recipient": player_id, "content": "房间中没有玩家，无法开始游戏局"}]
        
        try:
            # 获取房间中保存的剧本ID
            room_scenario_id = room_context.get_scenario_id()
            if not room_scenario_id:
                return await self._send_scenario_list(player_id, "请先设置剧本再开始游戏局！")
            
            # 获取或创建游戏局控制器
            match_context = await match_service.get_match_context(room_context)
            
            # 检查游戏是否已经在运行
            if match_context and await match_service.is_match_running(match_context):
                logger.warning(f"无法开始新游戏局: 当前已有进行中的游戏局 ID={match_context.match.id}")
                return [{"recipient": player_id, "content": f"无法开始游戏局: 当前已有进行中的游戏局"}]
            
            # 创建新的游戏局，使用房间中保存的剧本ID
            if not match_context:
                match_context, create_messages = await match_service.create_match(room_context, "新的冒险")
                logger.info(f"为开始游戏创建新游戏局: ID={match_context.match.id}")
            
            # 设置剧本（确保使用房间中保存的剧本）
            if not match_context.match.scenario_id:
                success, error_msg, scenario_messages = await match_service.set_scenario(match_context, room_context, room_scenario_id)
                if not success:
                    return [{"recipient": player_id, "content": f"设置剧本失败: {error_msg}"}]
                
            # 加载可选角色列表
            available_characters = await match_service.load_available_characters(match_context)
            
            # 构建可选角色列表消息
            character_msg = "【可选角色】\n"
            if available_characters:
                for char in available_characters:
                    char_name = char.get("name", "未知")
                    char_desc = char.get("description", "")
                    char_type = "主要角色" if char.get("is_main", True) else "次要角色"
                    character_msg += f"- {char_name} ({char_type}): {char_desc[:50]}...\n"
                character_msg += "\n使用 /选角色 [角色名] 选择你要扮演的角色"
            else:
                character_msg += "当前剧本没有可选角色\n"
            
            # 获取所有玩家列表
            all_players = room_context.list_players()
            player_names = [p.name for p in all_players]
            
            # 向所有玩家广播游戏已创建和角色选择消息
            messages = []
            
            # 通知房主
            messages.append({
                "recipient": player_id, 
                "content": f"游戏局已创建，使用剧本: {room_scenario_id}。请所有玩家选择角色后游戏将自动开始。"
            })
            
            # 向所有玩家广播角色选择消息
            for player in all_players:
                messages.append({
                    "recipient": player.id,
                    "content": f"房主已开始游戏，请选择你要扮演的角色。\n{character_msg}"
                })
            
            return messages
            
        except ValueError as e:
            logger.error(f"创建游戏局失败: {str(e)}")
            return [{"recipient": player_id, "content": f"无法开始游戏局: {str(e)}"}]
    
    async def _send_scenario_list(self, player_id: str, message: str) -> List[Dict[str, str]]:
        """发送剧本列表给玩家"""
        scenario_loader = ScenarioLoader()
        scenarios = scenario_loader.list_scenarios()
        
        # 构建剧本列表消息
        scenarios_msg = "可用剧本列表:\n"
        for s in scenarios:
            scenarios_msg += f"- {s['id']}: {s['name']}\n"
        
        # 发送提示消息
        return [{
            "recipient": player_id, 
            "content": f"{message}\n\n{scenarios_msg}\n使用命令 /剧本 [剧本ID] 设置剧本。"
        }]


class EndMatchCommand(GameCommand):
    """处理结束游戏局(match)事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        result = event.data.get("result", "玩家手动结束")
        
        logger.info(f"处理结束游戏局事件: 发起者={player_name}({player_id}), 结果={result}")
        
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
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
        
        # 结束游戏局
        success, end_messages = await match_service.end_match(match_context, result)
        if not success:
            return [{"recipient": player_id, "content": "结束游戏局失败，可能当前游戏局未在运行中"}]
        
        return end_messages


class SetScenarioCommand(GameCommand):
    """处理设置剧本事件的命令"""
    
    async def execute(self, event: SetScenarioEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: SetScenarioEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        scenario_id = event.data["scenario_id"]
        
        logger.info(f"处理设置剧本事件: 玩家ID={player_id}, 剧本ID={scenario_id}")
        
        # 获取服务
        room_service = self.service_provider.get_service(RoomService)
        match_service = self.service_provider.get_service(MatchService)
        
        # 获取玩家所在房间的控制器
        room_context = await room_service.get_player_room_context(player_id)
        if not room_context:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 检查是否为房主
        if room_context.room.host_id != player_id:
            return [{"recipient": player_id, "content": "只有房主才能设置剧本"}]
        
        # 设置房间的剧本
        room_context.set_scenario(scenario_id)
        
        # 获取或创建游戏局控制器
        match_context = await match_service.get_match_context(room_context)
        if not match_context:
            match_context, create_messages = await match_service.create_match(room_context, "新的冒险")
            logger.info(f"为设置剧本创建新游戏局: ID={match_context.match.id}")
        
        # 设置游戏局的剧本
        success, error_msg, scenario_messages = await match_service.set_scenario(match_context, room_context, scenario_id)
        if not success:
            # 获取可用剧本列表并发送
            scenario_loader = ScenarioLoader()
            scenarios = scenario_loader.list_scenarios()
            scenarios_msg = "可用剧本列表:\n"
            for s in scenarios:
                scenarios_msg += f"- {s['id']}: {s['name']}\n"
                
            return [{"recipient": player_id, "content": f"{error_msg}\n\n{scenarios_msg}"}]
            
        return scenario_messages


class PauseMatchCommand(GameCommand):
    """处理暂停游戏局事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        
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
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
        
        # 暂停游戏局
        success, pause_messages = await match_service.pause_match(match_context, room_context)
        if not success:
            return [{"recipient": player_id, "content": "暂停游戏局失败，可能当前游戏局未在运行中"}]
        
        return pause_messages


class ResumeMatchCommand(GameCommand):
    """处理恢复游戏局事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令
        
        Args:
            event: GameEvent - 事件对象
            
        Returns:
            List[Union[GameEvent, Dict[str, str]]]: 响应消息列表
        """
        player_id = event.data["player_id"]
        
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
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
        
        # 恢复游戏局
        success, resume_messages = await match_service.resume_match(match_context, room_context)
        if not success:
            return [{"recipient": player_id, "content": "恢复游戏局失败，可能当前游戏局未处于暂停状态"}]
        
        return resume_messages

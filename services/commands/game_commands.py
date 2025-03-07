import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import Room, Match, Player, Character, TurnType, TurnStatus, GameStatus, BaseTurn, DMTurn, DiceTurn
from core.room import RoomManager
from core.turn import TurnManager
from core.match import MatchManager
from adapters.base import GameEvent, DMNarrationEvent, SetScenarioEvent, PlayerActionEvent
from services.commands.base import GameCommand
from utils.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)

class CharacterActionCommand(GameCommand):
    """处理角色行动事件的命令"""
    
    async def execute(self, event: PlayerActionEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        from services.turn_service import TurnService
        
        player_id = event.data["player_id"]
        action = event.data["action"]
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 获取玩家对应的角色
        character = room_manager.get_character_by_player_id(player_id)
        if not character:
            return [{"recipient": player_id, "content": "找不到你的游戏角色，请尝试重新加入房间"}]
        
        # 获取游戏局管理器
        match_manager = MatchManager.get_current_match_manager(player_room, self.game_instance)
        if not match_manager:
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
            
        # 检查游戏局状态
        if match_manager.match.status != GameStatus.RUNNING:
            return [{"recipient": player_id, "content": f"当前游戏局未在运行中，状态: {match_manager.match.status}"}]
            
        # 获取回合管理器
        turn_manager = TurnManager(match_manager.match)
        current_turn = turn_manager.get_current_turn()
        
        # 检查是否有活动回合
        if not current_turn:
            return [{"recipient": player_id, "content": "当前没有活动回合"}]
            
        # 检查是否是玩家回合
        if current_turn.turn_type != TurnType.PLAYER:
            return []
        
        # 使用TurnService处理角色行动
        turn_service = TurnService(self.rule_engine)
        success, action_messages = await turn_service.process_player_action(
            player_id, 
            action, 
            current_turn, 
            turn_manager, 
            character
        )
        
        if not success:
            return action_messages
            
        # 检查回合是否完成
        if current_turn.status != TurnStatus.COMPLETED:
            return action_messages
            
        # 收集所有消息
        messages = action_messages.copy()
        
        # 使用TurnService转换到DM回合
        dm_turn, transition_messages = await turn_service.transition_to_dm_turn(match_manager.match, turn_manager)
        messages.extend(transition_messages)
        
        # 触发DM叙述，传入房间ID
        messages.append(DMNarrationEvent("", player_room.id))
        
        return messages

class StartMatchCommand(GameCommand):
    """处理开始游戏局(match)事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理开始游戏局事件: 发起者={player_name}({player_id})")
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 1. 检查房间中是否有玩家
        if not player_room.players:
            logger.warning(f"开始游戏局失败: 房间中没有玩家")
            return [{"recipient": player_id, "content": "房间中没有玩家，无法开始游戏局"}]
        
        try:
            # 2. 获取或创建游戏局管理器
            match_manager = MatchManager.get_current_match_manager(player_room, self.game_instance)
            
            # 3. 如果没有游戏局，创建一个新的并提示设置剧本
            if not match_manager:
                match_manager = MatchManager.create_match(player_room, self.game_instance, "新的冒险")
                return await self._send_scenario_list(player_id, "已创建游戏局，请先设置剧本再开始游戏局！")
            
            # 4. 检查游戏是否已经在运行
            if match_manager.match.status == GameStatus.RUNNING:
                logger.warning(f"无法开始新游戏局: 当前已有进行中的游戏局 ID={match_manager.match.id}")
                return [{"recipient": player_id, "content": f"无法开始游戏局: 当前已有进行中的游戏局"}]
            
            # 5. 检查是否已设置剧本
            if not match_manager.match.scenario_id:
                return await self._send_scenario_list(player_id, "请先设置剧本再开始游戏局！")
                
            # 6. 检查是否所有玩家都已选择角色
            all_selected, players_without_characters = match_manager.check_all_players_selected_character()
                    
            if not all_selected:
                # 如果有玩家未选择角色，提示选择角色
                player_list = ", ".join(players_without_characters)
                
                # 加载可选角色列表
                available_characters = match_manager.load_available_characters()
                
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
                
                return [
                    {"recipient": player_id, "content": f"以下玩家尚未选择角色: {player_list}，请先选择角色再开始游戏局！"},
                    {"recipient": player_id, "content": character_msg}
                ]
            
            # 7. 所有条件都满足，可以开始游戏
            # 使用MatchManager开始游戏局
            success = match_manager.start_match()
            if not success:
                return [{"recipient": player_id, "content": "开始游戏局失败，请检查游戏状态"}]
            
            # 获取回合管理器
            turn_manager = TurnManager(match_manager.match)
            
            # 创建第一个DM回合
            dm_turn = turn_manager.start_new_turn(TurnType.DM)
            logger.info(f"创建第一个DM回合: ID={dm_turn.id}")
            
            # 通知所有玩家游戏开始
            messages = []
            player_ids = [p.id for p in player_room.players]
            for pid in player_ids:
                logger.info(f"通知玩家游戏局开始: 玩家ID={pid}")
                messages.append({"recipient": pid, "content": f"游戏局已开始！DM {player_name} 正在准备第一个场景..."})
            
            # 触发DM叙述事件，传入房间ID
            logger.info("触发DM叙述事件")
            messages.append(DMNarrationEvent("", player_room.id))
            
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
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        result = event.data.get("result", "玩家手动结束")
        
        logger.info(f"处理结束游戏局事件: 发起者={player_name}({player_id}), 结果={result}")
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 获取游戏局管理器
        match_manager = MatchManager.get_current_match_manager(player_room, self.game_instance)
        if not match_manager:
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
        
        # 结束游戏局
        success = match_manager.end_match(result)
        if not success:
            return [{"recipient": player_id, "content": "结束游戏局失败，可能当前游戏局未在运行中"}]
        
        # 通知所有玩家游戏结束
        messages = []
        for p in player_room.players:
            messages.append({
                "recipient": p.id, 
                "content": f"游戏局已结束！结果: {result}"
            })
        
        return messages


class SetScenarioCommand(GameCommand):
    """处理设置剧本事件的命令"""
    
    async def execute(self, event: SetScenarioEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        scenario_id = event.data["scenario_id"]
        
        logger.info(f"处理设置剧本事件: 玩家ID={player_id}, 剧本ID={scenario_id}")
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 获取或创建游戏局管理器
        match_manager = MatchManager.get_current_match_manager(player_room, self.game_instance)
        if not match_manager:
            match_manager = MatchManager.create_match(player_room, self.game_instance, "新的冒险")
            logger.info(f"为设置剧本创建新游戏局: ID={match_manager.match.id}")
        
        # 检查剧本是否存在
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        
        if not scenario:
            # 获取可用剧本列表并发送
            scenarios = scenario_loader.list_scenarios()
            scenarios_msg = "可用剧本列表:\n"
            for s in scenarios:
                scenarios_msg += f"- {s['id']}: {s['name']}\n"
                
            return [{"recipient": player_id, "content": f"剧本不存在: {scenario_id}\n\n{scenarios_msg}"}]
            
        # 使用MatchManager设置剧本
        success = match_manager.set_scenario(scenario_id)
        if not success:
            return [{"recipient": player_id, "content": "设置剧本失败。剧本只能在游戏局开始前设置。"}]
            
        # 加载可选角色列表
        available_characters = match_manager.load_available_characters()
        
        # 构建剧本详情消息
        scenario_details = f"【剧本详情】\n"
        scenario_details += f"名称: {scenario.name}\n"
        scenario_details += f"背景: {scenario.world_background[:100]}...\n"
        
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
        
        messages = []
        # 通知所有玩家
        for p in player_room.players:
            messages.append({"recipient": p.id, "content": f"DM设置了新剧本: {scenario.name}"})
            messages.append({"recipient": p.id, "content": character_msg})
            
        # 给DM发送详细信息
        messages.append({"recipient": player_id, "content": scenario_details})
        
        # 如果当前是DM回合，触发DM叙述事件以更新场景，传入房间ID
        turn_manager = TurnManager(match_manager.match)
        current_turn = turn_manager.get_current_turn()
        if current_turn and current_turn.turn_type == TurnType.DM:
            messages.append(DMNarrationEvent("", player_room.id))
            
        return messages


class DMNarrationCommand(GameCommand):
    """处理DM叙述事件的命令"""
    
    async def execute(self, event: DMNarrationEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        from services.narration_service import NarrationService
        from services.turn_service import TurnService
        
        # 获取room_id
        room_id = event.data.get("room_id")
        active_room = None
        
        if room_id:
            # 如果提供了room_id，直接获取对应的房间
            active_room = self.game_instance.get_room(room_id)
        
        # 如果找不到活动房间，返回空列表
        if not active_room:
            logger.warning("找不到有进行中游戏的房间")
            return []
        
        # 获取游戏局管理器
        match_manager = MatchManager.get_current_match_manager(active_room, self.game_instance)
        if not match_manager:
            logger.warning("当前没有进行中的游戏局")
            return []
            
        # 检查游戏局状态
        if match_manager.match.status != GameStatus.RUNNING:
            logger.warning(f"游戏局未在运行中: ID={match_manager.match.id}, 状态={match_manager.match.status}")
            return []
            
        # 获取回合管理器
        turn_manager = TurnManager(match_manager.match)
        current_turn = turn_manager.get_current_turn()
        
        # 检查是否是DM回合
        if not current_turn or current_turn.turn_type != TurnType.DM:
            logger.warning("当前不是DM回合")
            return []
        
        # 使用服务层处理叙述逻辑
        narration_service = NarrationService(self.ai_service, self.rule_engine)
        turn_service = TurnService(self.rule_engine)
        
        # 准备AI上下文
        player_names = [p.name for p in active_room.players]
        player_ids = [p.id for p in active_room.players]
        
        # 获取上下文信息
        context = await narration_service.prepare_context(match_manager.match, current_turn, active_room.players)
        
        # 加载剧本（如果有）
        scenario = await narration_service.load_scenario(match_manager.match)
        
        # 调用AI服务
        response = await self.ai_service.generate_narration(context, scenario)
        
        # 处理AI响应
        messages = []
        
        # 处理位置、物品和剧情更新
        update_messages = await narration_service.process_ai_response(response, active_room, scenario)
        
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
                # 使用MatchManager结束游戏局
                result = notification.get("result", "AI决定结束游戏")
                match_manager.end_match(result)
                logger.info(f"游戏局已结束：ID={match_manager.match.id}, 结果={result}")
        
        # 将普通消息添加到返回列表
        messages.extend(regular_messages)
        
        # 处理回合转换和通知玩家
        turn_messages = await turn_service.handle_turn_transition(response, current_turn, turn_manager, player_ids)
        messages.extend(turn_messages)
        
        return messages

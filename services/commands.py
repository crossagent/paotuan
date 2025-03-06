import logging
import asyncio
from typing import List, Dict, Any, Optional, Union

from models.entities import Room, Match, TurnType, TurnStatus, GameStatus, BaseTurn, DMTurn, ActionTurn, DiceTurn
from core.game import GameInstance
from core.room import RoomManager
from core.turn import TurnManager
from core.rules import RuleEngine
from core.events import EventBus
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent, SetScenarioEvent, CreateRoomEvent, JoinRoomEvent, ListRoomsEvent
from services.ai_service import AIService
from utils.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)

class GameCommand:
    """游戏命令基类"""
    
    def __init__(self, game_instance: GameInstance, event_bus: EventBus, 
                 ai_service: AIService, rule_engine: RuleEngine):
        self.game_instance = game_instance
        self.event_bus = event_bus
        self.ai_service = ai_service
        self.rule_engine = rule_engine
        
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """执行命令，返回事件或消息列表"""
        raise NotImplementedError("子类必须实现execute方法")
        
    def _get_or_create_room(self) -> Room:
        """获取或创建房间，公共方法"""
        rooms = self.game_instance.list_rooms()
        if not rooms:
            return self.game_instance.create_room("默认房间")
        return rooms[0]
        
    def _get_room_by_id(self, room_id: str) -> Optional[Room]:
        """根据ID获取房间"""
        return self.game_instance.get_room(room_id)
        
    def _get_player_room(self, player_id: str) -> Optional[Room]:
        """获取玩家所在的房间"""
        return self.game_instance.get_player_room(player_id)
        
    def _get_player_current_match(self, player_id: str) -> Optional[Match]:
        """获取玩家当前的游戏局"""
        return self.game_instance.get_player_match(player_id)


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


class PlayerActionCommand(GameCommand):
    """处理玩家行动事件的命令"""
    
    async def execute(self, event: PlayerActionEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        action = event.data["action"]
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 检查是否有进行中的游戏局
        match = room_manager.get_current_match()
        if not match:
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
            
        # 获取回合管理器
        turn_manager = TurnManager(match)
        current_turn = turn_manager.get_current_turn()
        
        # 检查是否有活动回合
        if not current_turn:
            return [{"recipient": player_id, "content": "当前没有活动回合"}]
            
        # 检查是否是玩家回合
        if current_turn.turn_type != TurnType.PLAYER:
            return []
            
        # 处理玩家行动
        success = turn_manager.handle_player_action(player_id, action)
        if not success:
            return [{"recipient": player_id, "content": "无法处理你的行动"}]
            
        # 检查回合是否完成
        if current_turn.status != TurnStatus.COMPLETED:
            return []
            
        # 如果是掷骰子回合，处理掷骰子结果
        messages = []
        if isinstance(current_turn, DiceTurn):
            # 处理掷骰子结果
            dice_results = self.rule_engine.process_dice_turn_results(current_turn)
            
            # 通知所有玩家掷骰子结果
            result_message = "【掷骰子结果】\n"
            for result in dice_results.get("summary", []):
                player_name = next((p.name for p in player_room.players if p.id == result["player_id"]), result["player_id"])
                result_message += f"{player_name} 尝试 {result['action']}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
            
            for pid in [p.id for p in player_room.players]:
                messages.append({"recipient": pid, "content": result_message})
        
        # 转到DM回合
        turn_manager.complete_current_turn(TurnType.DM)
        
        # 创建DM回合
        dm_turn = turn_manager.start_new_turn(TurnType.DM)
        
        # 触发DM叙述，传入房间ID
        messages.append(DMNarrationEvent("", player_room.id))
        
        return messages


class StartGameCommand(GameCommand):
    """处理开始游戏事件的命令"""
    
    async def execute(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理开始游戏事件: 发起者={player_name}({player_id})")
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 1. 检查房间中是否有玩家
        if not player_room.players:
            logger.warning(f"开始游戏失败: 房间中没有玩家")
            return [{"recipient": player_id, "content": "房间中没有玩家，无法开始游戏"}]
        
        try:
            # 2. 获取或创建游戏局
            current_match = room_manager.get_current_match()
            
            # 3. 如果没有游戏局，创建一个新的并提示设置剧本
            if not current_match:
                current_match = room_manager.create_match("新的冒险")
                return await self._send_scenario_list(player_id, "已创建游戏局，请先设置剧本再开始游戏！")
            
            # 4. 检查游戏是否已经在运行
            if current_match.status == GameStatus.RUNNING:
                logger.warning(f"无法开始新游戏: 当前已有进行中的游戏局 ID={current_match.id}")
                return [{"recipient": player_id, "content": f"无法开始游戏: 当前已有进行中的游戏局"}]
            
            # 5. 检查是否已设置剧本
            if not current_match.scenario_id:
                return await self._send_scenario_list(player_id, "请先设置剧本再开始游戏！")
            
            # 6. 所有条件都满足，可以开始游戏
            # 设置游戏状态为运行中
            current_match.status = GameStatus.RUNNING
            logger.info(f"游戏局开始运行: ID={current_match.id}, 状态={current_match.status}")
            
            # 获取回合管理器
            turn_manager = TurnManager(current_match)
            
            # 创建第一个DM回合
            dm_turn = turn_manager.start_new_turn(TurnType.DM)
            logger.info(f"创建第一个DM回合: ID={dm_turn.id}")
            
            # 通知所有玩家游戏开始
            messages = []
            player_ids = [p.id for p in player_room.players]
            for pid in player_ids:
                logger.info(f"通知玩家游戏开始: 玩家ID={pid}")
                messages.append({"recipient": pid, "content": f"游戏已开始！DM {player_name} 正在准备第一个场景..."})
            
            # 触发DM叙述事件，传入房间ID
            logger.info("触发DM叙述事件")
            messages.append(DMNarrationEvent("", player_room.id))
            
            return messages
            
        except ValueError as e:
            logger.error(f"创建游戏局失败: {str(e)}")
            return [{"recipient": player_id, "content": f"无法开始游戏: {str(e)}"}]
    
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
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 检查是否有游戏局，如果没有则创建
        current_match = room_manager.get_current_match()
        if not current_match:
            current_match = room_manager.create_match("新的冒险")
            logger.info(f"为设置剧本创建新游戏局: ID={current_match.id}")
        
        # 检查游戏状态，如果已经开始则不能更换剧本
        if current_match.status == GameStatus.RUNNING:
            return [{"recipient": player_id, "content": "无法更换剧本：游戏已经开始。剧本只能在游戏开始前设置。"}]
        
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
            
        # 设置剧本
        success = room_manager.set_scenario(scenario_id)
        if not success:
            return [{"recipient": player_id, "content": "设置剧本失败。剧本只能在游戏开始前设置。"}]
            
        # 构建剧本详情消息
        scenario_details = f"【剧本详情】\n"
        scenario_details += f"名称: {scenario.name}\n"
        scenario_details += f"背景: {scenario.background[:100]}...\n"
        scenario_details += f"目标: {scenario.goal}\n"
        
        messages = []
        # 通知所有玩家
        for p in player_room.players:
            messages.append({"recipient": p.id, "content": f"DM设置了新剧本: {scenario.name}"})
            
        # 给DM发送详细信息
        messages.append({"recipient": player_id, "content": scenario_details})
        
        # 如果当前是DM回合，触发DM叙述事件以更新场景，传入房间ID
        turn_manager = TurnManager(current_match)
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
            if active_room and active_room.current_match_id:
                # 验证房间中有进行中的游戏
                match_running = False
                for match in active_room.matches:
                    if match.id == active_room.current_match_id and match.status == GameStatus.RUNNING:
                        match_running = True
                        break
                if not match_running:
                    active_room = None
                    logger.warning(f"指定的房间 {room_id} 没有进行中的游戏")
        else:
            # 如果没有提供room_id，则需要遍历查找有进行中游戏的房间
            logger.warning("DMNarrationEvent没有提供room_id，将遍历查找活跃房间")
            return []
        
        # 如果找不到活动房间，返回空列表
        if not active_room:
            logger.warning("找不到有进行中游戏的房间")
            return []
        
        # 创建房间管理器
        room_manager = RoomManager(active_room, self.game_instance)
        
        # 检查是否有进行中的游戏局
        match = room_manager.get_current_match()
        if not match:
            logger.warning("当前没有进行中的游戏局")
            return []
            
        # 获取回合管理器
        turn_manager = TurnManager(match)
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
        context = await narration_service.prepare_context(match, current_turn, active_room.players)
        
        # 加载剧本（如果有）
        scenario = await narration_service.load_scenario(match)
        
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
                # 更新Match状态为结束
                if match:
                    match.status = GameStatus.FINISHED
                    if "result" in notification:
                        match.game_state["result"] = notification["result"]
                    logger.info(f"Match已结束：ID={match.id}, 结果={notification.get('result', 'unknown')}")
        
        # 将普通消息添加到返回列表
        messages.extend(regular_messages)
        
        # 处理回合转换和通知玩家
        turn_messages = await turn_service.handle_turn_transition(response, current_turn, turn_manager, player_ids)
        messages.extend(turn_messages)
        
        return messages


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


class CommandFactory:
    """命令工厂，用于创建命令对象"""
    
    def __init__(self, game_instance: GameInstance, event_bus: EventBus, 
                 ai_service: AIService, rule_engine: RuleEngine):
        self.game_instance = game_instance
        self.event_bus = event_bus
        self.ai_service = ai_service
        self.rule_engine = rule_engine
        
    def create_command(self, event_type: str) -> GameCommand:
        """根据事件类型创建对应的命令对象"""
        if event_type == "PLAYER_JOINED":
            return PlayerJoinedCommand(self.game_instance, self.event_bus, 
                                      self.ai_service, self.rule_engine)
        elif event_type == "PLAYER_ACTION":
            return PlayerActionCommand(self.game_instance, self.event_bus, 
                                      self.ai_service, self.rule_engine)
        elif event_type == "START_MATCH":
            return StartGameCommand(self.game_instance, self.event_bus, 
                                   self.ai_service, self.rule_engine)
        elif event_type == "SET_SCENARIO":
            return SetScenarioCommand(self.game_instance, self.event_bus, 
                                     self.ai_service, self.rule_engine)
        elif event_type == "DM_NARRATION":
            return DMNarrationCommand(self.game_instance, self.event_bus, 
                                     self.ai_service, self.rule_engine)
        elif event_type == "CREATE_ROOM":
            return CreateRoomCommand(self.game_instance, self.event_bus, 
                                    self.ai_service, self.rule_engine)
        elif event_type == "JOIN_ROOM":
            return JoinRoomCommand(self.game_instance, self.event_bus, 
                                  self.ai_service, self.rule_engine)
        elif event_type == "LIST_ROOMS":
            return ListRoomsCommand(self.game_instance, self.event_bus, 
                                   self.ai_service, self.rule_engine)
        else:
            raise ValueError(f"未知事件类型: {event_type}")

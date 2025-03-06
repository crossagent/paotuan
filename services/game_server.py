import asyncio
import logging
from typing import List, Union
from models.entities import Room, TurnType, TurnStatus, GameStatus, BaseTurn, DMTurn, ActionTurn, DiceTurn
from core.game import GameInstance
from core.room import RoomManager
from core.turn import TurnManager
from core.rules import RuleEngine
from core.events import EventBus
from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent, SetScenarioEvent
from services.ai_service import AIService
from utils.inspector import GameStateInspector
from utils.web_inspector import WebInspector

logger = logging.getLogger(__name__)

class GameServer:
    """游戏服务器"""
    
    def __init__(self, ai_service: AIService):
        self.game_instance = GameInstance("main_game")
        self.adapters: List[MessageAdapter] = []
        self.ai_service = ai_service
        self.rule_engine = RuleEngine()
        self.event_bus = EventBus()
        self.running = False
        
        # 初始化状态检查器
        self.state_inspector = GameStateInspector(self.game_instance)
        self.web_inspector = WebInspector(self.state_inspector)
        
        # 注册事件处理器
        self._register_event_handlers()
    
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        self.event_bus.subscribe("PLAYER_JOINED", self._handle_player_joined)
        self.event_bus.subscribe("PLAYER_ACTION", self._handle_player_action)
        self.event_bus.subscribe("DM_NARRATION", self._handle_dm_narration)
        self.event_bus.subscribe("START_MATCH", self._handle_start_game)
        self.event_bus.subscribe("SET_SCENARIO", self._handle_set_scenario)
    
    async def _handle_player_joined(self, event: PlayerJoinedEvent) -> List[GameEvent]:
        """处理玩家加入事件"""
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理玩家加入事件: 玩家={player_name}({player_id})")
        
        # 获取房间
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        # 添加玩家
        player = room_manager.add_player(player_id, player_name)
        
        # 发送消息给玩家
        logger.info(f"发送加入成功消息给玩家: {player_name}({player_id}), 房间={room.name}")
        await self.send_message(player_id, f"你已成功加入房间: {room.name}")
        
        return []
    
    async def _handle_player_action(self, event: PlayerActionEvent) -> List[GameEvent]:
        """处理玩家行动事件"""
        player_id = event.data["player_id"]
        action = event.data["action"]
        
        # 获取房间和游戏局
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        # 检查是否有进行中的游戏局
        match = room_manager.get_current_match()
        if not match:
            await self.send_message(player_id, "当前没有进行中的游戏局")
            return []
            
        # 获取回合管理器
        turn_manager = TurnManager(match)
        current_turn = turn_manager.get_current_turn()
        
        # 检查是否有活动回合
        if not current_turn:
            await self.send_message(player_id, "当前没有活动回合")
            return []
            
        # 检查是否是玩家回合
        if current_turn.turn_type != TurnType.PLAYER:
            return []
            
        # 处理玩家行动
        success = turn_manager.handle_player_action(player_id, action)
        if not success:
            await self.send_message(player_id, "无法处理你的行动")
            return []
            
        # 检查回合是否完成
        if current_turn.status != TurnStatus.COMPLETED:
            return []
            
        # 如果是掷骰子回合，处理掷骰子结果
        if isinstance(current_turn, DiceTurn):
            # 处理掷骰子结果
            dice_results = self.rule_engine.process_dice_turn_results(current_turn)
            
            # 通知所有玩家掷骰子结果
            result_message = "【掷骰子结果】\n"
            for result in dice_results.get("summary", []):
                player_name = next((p.name for p in room.players if p.id == result["player_id"]), result["player_id"])
                result_message += f"{player_name} 尝试 {result['action']}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
            
            for pid in [p.id for p in room.players]:
                await self.send_message(pid, result_message)
        
        # 转到DM回合
        turn_manager.complete_current_turn(TurnType.DM)
        
        # 创建DM回合
        dm_turn = turn_manager.start_new_turn(TurnType.DM)
        
        # 触发DM叙述
        return [DMNarrationEvent("")]
    
    async def _handle_start_game(self, event: GameEvent) -> List[GameEvent]:
        """处理DM开启游戏事件"""
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理开始游戏事件: 发起者={player_name}({player_id})")
        
        # 获取房间
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        # 1. 检查房间中是否有玩家
        if not room.players:
            logger.warning(f"开始游戏失败: 房间中没有玩家")
            await self.send_message(player_id, "房间中没有玩家，无法开始游戏")
            return []
        
        try:
            # 2. 获取或创建游戏局
            current_match = room_manager.get_current_match()
            
            # 3. 如果没有游戏局，创建一个新的并提示设置剧本
            if not current_match:
                current_match = room_manager.create_match("新的冒险")
                await self._send_scenario_list(player_id, "已创建游戏局，请先设置剧本再开始游戏！")
                return []
            
            # 4. 检查游戏是否已经在运行
            if current_match.status == GameStatus.RUNNING:
                logger.warning(f"无法开始新游戏: 当前已有进行中的游戏局 ID={current_match.id}")
                await self.send_message(player_id, f"无法开始游戏: 当前已有进行中的游戏局")
                return []
            
            # 5. 检查是否已设置剧本
            if not current_match.scenario_id:
                await self._send_scenario_list(player_id, "请先设置剧本再开始游戏！")
                return []
            
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
            player_ids = [p.id for p in room.players]
            for pid in player_ids:
                logger.info(f"通知玩家游戏开始: 玩家ID={pid}")
                await self.send_message(pid, f"游戏已开始！DM {player_name} 正在准备第一个场景...")
            
            # 触发DM叙述事件
            logger.info("触发DM叙述事件")
            return [DMNarrationEvent("")]
            
        except ValueError as e:
            logger.error(f"创建游戏局失败: {str(e)}")
            await self.send_message(player_id, f"无法开始游戏: {str(e)}")
            return []
    
    async def _send_scenario_list(self, player_id: str, message: str) -> None:
        """发送剧本列表给玩家"""
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenarios = scenario_loader.list_scenarios()
        
        # 构建剧本列表消息
        scenarios_msg = "可用剧本列表:\n"
        for s in scenarios:
            scenarios_msg += f"- {s['id']}: {s['name']}\n"
        
        # 发送提示消息
        await self.send_message(
            player_id, 
            f"{message}\n\n{scenarios_msg}\n使用命令 /剧本 [剧本ID] 设置剧本。"
        )
    
    async def _handle_set_scenario(self, event: SetScenarioEvent) -> List[GameEvent]:
        """处理设置剧本事件"""
        player_id = event.data["player_id"]
        scenario_id = event.data["scenario_id"]
        
        logger.info(f"处理设置剧本事件: 玩家ID={player_id}, 剧本ID={scenario_id}")
        
        # 获取房间
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        # 检查是否有游戏局，如果没有则创建
        current_match = room_manager.get_current_match()
        if not current_match:
            current_match = room_manager.create_match("新的冒险")
            logger.info(f"为设置剧本创建新游戏局: ID={current_match.id}")
        
        # 检查游戏状态，如果已经开始则不能更换剧本
        if current_match.status == GameStatus.RUNNING:
            await self.send_message(player_id, "无法更换剧本：游戏已经开始。剧本只能在游戏开始前设置。")
            return []
        
        # 检查剧本是否存在
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        
        if not scenario:
            # 获取可用剧本列表并发送
            scenarios = scenario_loader.list_scenarios()
            scenarios_msg = "可用剧本列表:\n"
            for s in scenarios:
                scenarios_msg += f"- {s['id']}: {s['name']}\n"
                
            await self.send_message(player_id, f"剧本不存在: {scenario_id}\n\n{scenarios_msg}")
            return []
            
        # 设置剧本
        success = room_manager.set_scenario(scenario_id)
        if not success:
            await self.send_message(player_id, "设置剧本失败。剧本只能在游戏开始前设置。")
            return []
            
        # 构建剧本详情消息
        scenario_details = f"【剧本详情】\n"
        scenario_details += f"名称: {scenario.name}\n"
        scenario_details += f"背景: {scenario.background[:100]}...\n"
        scenario_details += f"目标: {scenario.goal}\n"
        
        # 通知所有玩家
        for p in room.players:
            await self.send_message(p.id, f"DM设置了新剧本: {scenario.name}")
            
        # 给DM发送详细信息
        await self.send_message(player_id, scenario_details)
        
        # 如果当前是DM回合，触发DM叙述事件以更新场景
        turn_manager = TurnManager(current_match)
        current_turn = turn_manager.get_current_turn()
        if current_turn and current_turn.turn_type == TurnType.DM:
            return [DMNarrationEvent("")]
            
        return []
    
    async def _handle_dm_narration(self, event: DMNarrationEvent) -> List[GameEvent]:
        """处理DM叙述事件"""
        # 获取房间和游戏局
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
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
        
        # 准备AI上下文
        player_names = [p.name for p in room.players]
        player_ids = [p.id for p in room.players]
        
        # 获取上下文信息
        context = self._prepare_narration_context(match, current_turn, room.players, player_names, player_ids)
        
        # 加载剧本（如果有）
        scenario = self._load_scenario(match)
        
        # 调用AI服务
        response = await self.ai_service.generate_narration(context, scenario)
        
        # 处理AI响应
        await self._process_location_updates(response, room.players, scenario)
        await self._process_item_updates(response, room.players, scenario)
        await self._process_plot_progress(response, scenario, player_ids)
        
        # 处理回合转换和通知玩家
        await self._handle_turn_transition(response, current_turn, turn_manager, player_ids)
        
        return []
        
    def _prepare_narration_context(self, match, current_turn, players, player_names, player_ids):
        """准备AI叙述的上下文信息"""
        previous_actions = ""
        dice_results = None
        
        # 获取上一个回合的玩家行动
        if len(match.turns) > 1:
            prev_turn = [t for t in match.turns if t.id != current_turn.id][-1]
            if prev_turn.turn_type == TurnType.PLAYER:
                if isinstance(prev_turn, DiceTurn):
                    # 如果上一回合是掷骰子回合，获取掷骰子结果
                    dice_results = self.rule_engine.process_dice_turn_results(prev_turn)
                elif isinstance(prev_turn, ActionTurn):
                    # 普通行动回合，获取玩家行动
                    actions = []
                    for pid, action in prev_turn.actions.items():
                        player_name = next((p.name for p in players if p.id == pid), pid)
                        actions.append(f"{player_name}: {action}")
                    previous_actions = "\n".join(actions)
        
        # 准备生成上下文
        return {
            "current_scene": match.scene,
            "players": ", ".join(player_names),
            "player_actions": previous_actions or "没有玩家行动",
            "history": "（历史记录将在这里添加）", # 实际实现需要保存历史记录
            "dice_results": dice_results,  # 添加掷骰子结果
            "player_ids": player_ids  # 添加玩家ID列表
        }
        
    def _load_scenario(self, match):
        """加载剧本（如果有）"""
        if not match.scenario_id:
            return None
            
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(match.scenario_id)
        
        if scenario:
            logger.info(f"加载剧本: {scenario.name}, 当前剧情节点: {scenario.current_plot_point + 1}/{len(scenario.plot_points)}")
            
        return scenario
        
    async def _process_location_updates(self, response, players, scenario):
        """处理位置更新"""
        if not hasattr(response, 'location_updates') or not response.location_updates:
            return
            
        for location_update in response.location_updates:
            player_id = location_update.player_id
            new_location = location_update.new_location
            
            # 更新玩家位置
            for player in players:
                if player.id == player_id:
                    player.location = new_location
                    logger.info(f"更新玩家位置: 玩家={player.name}({player_id}), 新位置={new_location}")
                    
                    # 如果有剧本，也更新剧本中的玩家位置
                    if scenario:
                        scenario.player_location = new_location
                        from utils.scenario_loader import ScenarioLoader
                        scenario_loader = ScenarioLoader()
                        scenario_loader.save_scenario(scenario)
                        logger.info(f"更新剧本中的玩家位置: 新位置={new_location}")
                    break
                    
    async def _process_item_updates(self, response, players, scenario):
        """处理物品更新"""
        if not hasattr(response, 'item_updates') or not response.item_updates:
            return
            
        for item_update in response.item_updates:
            player_id = item_update.player_id
            item = item_update.item
            action = item_update.action
            
            # 更新玩家物品
            for player in players:
                if player.id == player_id:
                    if action == "add" and item not in player.items:
                        player.items.append(item)
                        logger.info(f"玩家获得物品: 玩家={player.name}({player_id}), 物品={item}")
                        
                        # 如果有剧本，也更新剧本中的已收集道具
                        if scenario and item not in scenario.collected_items:
                            scenario.collected_items.append(item)
                            from utils.scenario_loader import ScenarioLoader
                            scenario_loader = ScenarioLoader()
                            scenario_loader.save_scenario(scenario)
                            logger.info(f"更新剧本中的已收集道具: 添加物品={item}")
                    elif action == "remove" and item in player.items:
                        player.items.remove(item)
                        logger.info(f"玩家失去物品: 玩家={player.name}({player_id}), 物品={item}")
                        
                        # 如果有剧本，也更新剧本中的已收集道具
                        if scenario and item in scenario.collected_items:
                            scenario.collected_items.remove(item)
                            from utils.scenario_loader import ScenarioLoader
                            scenario_loader = ScenarioLoader()
                            scenario_loader.save_scenario(scenario)
                            logger.info(f"更新剧本中的已收集道具: 移除物品={item}")
                    break
                    
    async def _process_plot_progress(self, response, scenario, player_ids):
        """处理剧情进度更新"""
        if not hasattr(response, 'plot_progress') or response.plot_progress is None or not scenario:
            return
            
        if response.plot_progress > scenario.current_plot_point:
            old_plot_point = scenario.current_plot_point
            scenario.current_plot_point = min(response.plot_progress, len(scenario.plot_points) - 1)
            from utils.scenario_loader import ScenarioLoader
            scenario_loader = ScenarioLoader()
            scenario_loader.save_scenario(scenario)
            logger.info(f"更新剧情进度: 从 {old_plot_point + 1} 到 {scenario.current_plot_point + 1}")
            
            # 通知所有玩家剧情进展
            progress_message = f"【剧情进展】\n{scenario.plot_points[scenario.current_plot_point]}"
            for pid in player_ids:
                await self.send_message(pid, progress_message)
                
    async def _handle_turn_transition(self, response, current_turn, turn_manager, player_ids):
        """处理回合转换和通知玩家"""
        narration = response.narration
        
        # 保存DM叙述到DMTurn对象
        if isinstance(current_turn, DMTurn):
            current_turn.narration = narration
        
        # 完成DM回合，准备下一个玩家回合
        turn_manager.complete_current_turn(TurnType.PLAYER, response.active_players)
        
        # 根据是否需要骰子检定创建不同类型的回合
        if response.need_dice_roll and response.difficulty:
            # 创建新的掷骰子回合
            action_desc = response.action_desc or "行动"
            turn_manager.start_new_turn(
                TurnType.PLAYER, 
                response.active_players,
                turn_mode="dice",
                difficulty=response.difficulty,
                action_desc=action_desc
            )
            
            # 通知所有玩家
            for player_id in player_ids:
                await self.send_message(player_id, narration)
            
            # 通知激活玩家
            for player_id in response.active_players:
                await self.send_message(player_id, f"需要进行 {action_desc} 的骰子检定，难度为 {response.difficulty}。请描述你的具体行动。")
        else:
            # 创建新的普通玩家回合
            turn_manager.start_new_turn(
                TurnType.PLAYER, 
                response.active_players,
                turn_mode="action"
            )
            
            # 通知所有玩家
            for player_id in player_ids:
                await self.send_message(player_id, narration)
            
            # 通知激活玩家
            for player_id in response.active_players:
                await self.send_message(player_id, "轮到你行动了，请输入你的行动。")

    def _get_or_create_room(self) -> Room:
        """获取或创建房间"""
        rooms = self.game_instance.list_rooms()
        if not rooms:
            return self.game_instance.create_room("默认房间")
        return rooms[0]

    def register_adapter(self, adapter: MessageAdapter) -> None:
        """注册消息适配器"""
        self.adapters.append(adapter)

    async def start(self) -> None:
        """启动服务器"""
        # 检查服务器是否已经在运行
        if self.running:
            logger.warning("服务器已经在运行")
            return
            
        # 启动Web状态检查器
        await self.web_inspector.start()
            
        # 启动所有适配器
        for adapter in self.adapters:
            await adapter.start()
            
        # 标记为运行中
        self.running = True
        
        # 启动消息处理循环
        asyncio.create_task(self._message_loop())
        
        logger.info("游戏服务器已启动")

    async def stop(self) -> None:
        """停止服务器"""
        # 如果服务器已经停止，直接返回
        if not self.running:
            return
            
        self.running = False
        
        # 停止所有适配器
        for adapter in self.adapters:
            await adapter.stop()
            
        # 停止Web状态检查器
        await self.web_inspector.stop()
            
        logger.info("游戏服务器已停止")

    async def _message_loop(self) -> None:
        """消息处理循环"""
        while self.running:
            # 从所有适配器接收消息
            for adapter in self.adapters:
                event = await adapter.receive_message()
                if event:
                    # 发布到事件总线
                    await self._process_event(event)
                    
            # 适当休眠以避免CPU占用过高
            await asyncio.sleep(0.1)

    async def _process_event(self, event: GameEvent) -> None:
        """处理事件"""
        try:
            logger.info(f"处理事件: 类型={event.event_type}, 数据={event.data}")
            
            # 发布到事件总线 - 使用await等待异步结果
            responses = await self.event_bus.publish(event)
            
            # 处理响应
            for response in responses:
                if isinstance(response, GameEvent):
                    logger.info(f"处理响应事件: 类型={response.event_type}")
                    await self._process_event(response)
        except Exception as e:
            logger.exception(f"处理事件失败: {str(e)}")

    async def send_message(self, player_id: str, content: str) -> None:
        """发送消息给玩家"""
        logger.info(f"发送消息给玩家: ID={player_id}, 内容前20字符='{content[:20]}...'")
        for adapter in self.adapters:
            await adapter.send_message(player_id, content)

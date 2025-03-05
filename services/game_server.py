import asyncio
import logging
from typing import List
from models.entities import Room, TurnType, TurnStatus, GameStatus
from core.game import GameInstance
from core.room import RoomManager
from core.turn import TurnManager
from core.rules import RuleEngine
from core.events import EventBus
from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent
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
    
    async def _handle_player_joined(self, event: PlayerJoinedEvent) -> List[GameEvent]:
        """处理玩家加入事件"""
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        # 获取房间
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        # 添加玩家
        player = room_manager.add_player(player_id, player_name)
        
        # 发送消息给玩家
        await self.send_message(player_id, f"你已成功加入房间: {room.name}")
        
        return []
    
    async def _handle_player_action(self, event: PlayerActionEvent) -> List[GameEvent]:
        """处理玩家行动事件"""
        player_id = event.data["player_id"]
        action = event.data["action"]
        
        # 获取房间和游戏局
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        match = room_manager.get_current_match()
        if not match:
            await self.send_message(player_id, "当前没有进行中的游戏局")
            return []
            
        # 获取回合管理器
        turn_manager = TurnManager(match)
        current_turn = turn_manager.get_current_turn()
        
        if not current_turn:
            await self.send_message(player_id, "当前没有活动回合")
            return []
            
        # 处理玩家行动
        if current_turn.turn_type == TurnType.PLAYER:
            success = turn_manager.handle_player_action(player_id, action)
            if not success:
                await self.send_message(player_id, "无法处理你的行动")
                return []
                
            # 检查回合是否完成
            if current_turn.status == TurnStatus.COMPLETED:
                # 如果是掷骰子回合，处理掷骰子结果
                if current_turn.turn_mode == "dice":
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
        
        return []
    
    async def _handle_start_game(self, event: GameEvent) -> List[GameEvent]:
        """处理DM开启游戏事件"""
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        # 获取房间
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        # 检查房间中是否有玩家
        if not room.players:
            await self.send_message(player_id, "房间中没有玩家，无法开始游戏")
            return []
        
        # 创建新的游戏局
        try:
            match = room_manager.create_match("新的冒险")
            match.status = GameStatus.RUNNING
            
            # 获取回合管理器
            turn_manager = TurnManager(match)
            
            # 创建第一个DM回合
            dm_turn = turn_manager.start_new_turn(TurnType.DM)
            
            # 通知所有玩家游戏开始
            player_ids = [p.id for p in room.players]
            for pid in player_ids:
                await self.send_message(pid, f"游戏已开始！DM {player_name} 正在准备第一个场景...")
            
            # 触发DM叙述事件
            return [DMNarrationEvent("")]
        except ValueError as e:
            await self.send_message(player_id, f"无法开始游戏: {str(e)}")
            return []
    
    async def _handle_dm_narration(self, event: DMNarrationEvent) -> List[GameEvent]:
        """处理DM叙述事件"""
        # 获取房间和游戏局
        room = self._get_or_create_room()
        room_manager = RoomManager(room)
        
        match = room_manager.get_current_match()
        if not match:
            logger.warning("当前没有进行中的游戏局")
            return []
            
        # 获取回合管理器
        turn_manager = TurnManager(match)
        current_turn = turn_manager.get_current_turn()
        
        if not current_turn or current_turn.turn_type != TurnType.DM:
            logger.warning("当前不是DM回合")
            return []
        
        # 准备AI上下文
        player_names = [p.name for p in room.players]
        player_ids = [p.id for p in room.players]
        
        # 获取上一个回合的玩家行动
        previous_actions = ""
        dice_results = None
        
        if len(match.turns) > 1:
            prev_turn = [t for t in match.turns if t.id != current_turn.id][-1]
            if prev_turn.turn_type == TurnType.PLAYER:
                if prev_turn.turn_mode == "dice":
                    # 如果上一回合是掷骰子回合，获取掷骰子结果
                    dice_results = self.rule_engine.process_dice_turn_results(prev_turn)
                    # 不需要设置previous_actions，因为掷骰子回合的行动已经包含在dice_results中
                else:
                    # 普通行动回合，获取玩家行动
                    actions = []
                    for pid, action in prev_turn.actions.items():
                        player_name = next((p.name for p in room.players if p.id == pid), pid)
                        actions.append(f"{player_name}: {action}")
                    previous_actions = "\n".join(actions)
        
        # 准备生成上下文
        context = {
            "current_scene": match.scene,
            "players": ", ".join(player_names),
            "player_actions": previous_actions or "没有玩家行动",
            "history": "（历史记录将在这里添加）", # 实际实现需要保存历史记录
            "dice_results": dice_results,  # 添加掷骰子结果
            "player_ids": player_ids  # 添加玩家ID列表
        }
        
        # 调用AI服务
        response = await self.ai_service.generate_narration(context)
        
        # 处理AI响应
        if response.need_dice_roll and response.difficulty:
            # 需要骰子检定，创建掷骰子回合
            narration = response.narration
            
            # 保存DM叙述
            current_turn.actions["dm_narration"] = narration
            
            # 完成DM回合，准备下一个玩家回合
            turn_manager.complete_current_turn(TurnType.PLAYER, response.active_players)
            
            # 创建新的掷骰子回合
            player_turn = turn_manager.start_new_turn(
                TurnType.PLAYER, 
                response.active_players,
                turn_mode="dice",
                difficulty=response.difficulty
            )
            
            # 通知所有玩家
            for player_id in player_ids:
                await self.send_message(player_id, narration)
            
            # 通知激活玩家
            for player_id in response.active_players:
                action_desc = response.action_desc or "行动"
                await self.send_message(player_id, f"需要进行 {action_desc} 的骰子检定，难度为 {response.difficulty}。请描述你的具体行动。")
        else:
            # 普通回合，不需要骰子检定
            narration = response.narration
            
            # 保存DM叙述
            current_turn.actions["dm_narration"] = narration
            
            # 完成DM回合，准备下一个玩家回合
            turn_manager.complete_current_turn(TurnType.PLAYER, response.active_players)
            
            # 创建新的普通玩家回合
            player_turn = turn_manager.start_new_turn(
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
        
        return []

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
            # 发布到事件总线 - 使用await等待异步结果
            responses = await self.event_bus.publish(event)
            
            # 处理响应
            for response in responses:
                if isinstance(response, GameEvent):
                    await self._process_event(response)
        except Exception as e:
            logger.exception(f"处理事件失败: {str(e)}")

    async def send_message(self, player_id: str, content: str) -> None:
        """发送消息给玩家"""
        for adapter in self.adapters:
            await adapter.send_message(player_id, content)

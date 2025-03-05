import asyncio
import logging
from typing import List
from models.entities import Room, TurnType, TurnStatus
from core.game import GameInstance
from core.room import RoomManager
from core.turn import TurnManager
from core.rules import RuleEngine
from core.events import EventBus
from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent
from services.ai_service import AIService

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
        
        # 注册事件处理器
        self._register_event_handlers()
    
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        self.event_bus.subscribe("PLAYER_JOINED", self._handle_player_joined)
        self.event_bus.subscribe("PLAYER_ACTION", self._handle_player_action)
        self.event_bus.subscribe("DM_NARRATION", self._handle_dm_narration)
    
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
                # 转到DM回合
                turn_manager.complete_current_turn(TurnType.DM)
                
                # 创建DM回合
                dm_turn = turn_manager.start_new_turn(TurnType.DM)
                
                # 触发DM叙述
                return [DMNarrationEvent("")]
        
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
        if len(match.turns) > 1:
            prev_turn = [t for t in match.turns if t.id != current_turn.id][-1]
            if prev_turn.turn_type == TurnType.PLAYER:
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
            "history": "（历史记录将在这里添加）" # 实际实现需要保存历史记录
        }
        
        # 调用AI服务
        response = await self.ai_service.generate_narration(context)
        
        # 处理AI响应
        if response.need_dice_roll and response.difficulty:
            # 处理需要骰子检定的情况
            # 这里只是简化处理，实际可能需要更复杂的逻辑
            success, roll = self.rule_engine.handle_dice_check(
                response.action_desc or "未知行动",
                response.difficulty
            )
            
            narration = f"【系统】进行了{response.action_desc}检定，难度{response.difficulty}，骰子结果{roll}，{'成功' if success else '失败'}。\n"
            narration += response.narration
        else:
            narration = response.narration
        
        # 保存DM叙述
        current_turn.actions["dm_narration"] = narration
        
        # 完成DM回合，准备下一个玩家回合
        turn_manager.complete_current_turn(TurnType.PLAYER, response.active_players)
        
        # 创建新的玩家回合
        player_turn = turn_manager.start_new_turn(TurnType.PLAYER, response.active_players)
        
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

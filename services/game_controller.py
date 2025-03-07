import asyncio
import logging
from typing import List, Dict, Any, Union

from models.entities import Room
from core.game_state import GameState
from core.rules import RuleEngine
from core.events import EventBus, EventObserver
from adapters.base import MessageAdapter, GameEvent
from services.ai_service import AIService
from utils.inspector import GameStateInspector
from utils.web_inspector import WebInspector
from services.commands.factory import CommandFactory

logger = logging.getLogger(__name__)

class GameController:
    """游戏控制器 - 负责系统协调、事件处理和适配器管理"""
    
    def __init__(self, ai_service: AIService):
        self.game_state = GameState("main_game")
        self.adapters: List[MessageAdapter] = []
        self.rule_engine = RuleEngine()
        self.event_bus = EventBus()
        self.running = False
        
        # 初始化服务
        self.ai_service = ai_service
        
        # 命令工厂 - 使用新的构造函数
        self.command_factory = CommandFactory(
            self.game_state, 
            self.event_bus,
            self.ai_service,
            self.rule_engine
        )
        
        # 初始化状态检查器
        self.state_inspector = GameStateInspector(self.game_state)
        self.web_inspector = WebInspector(self.state_inspector)
    
    async def _handle_event(self, event: GameEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        """使用命令模式处理事件"""
        try:
            # 创建对应的命令对象
            command = self.command_factory.create_command(event.event_type)
            
            # 执行命令
            return await command.execute(event)
        except ValueError as e:
            logger.error(f"处理事件失败: {str(e)}")
            if "player_id" in event.data:
                return [{"recipient": event.data["player_id"], "content": f"处理请求失败: {str(e)}"}]
            return []

    def register_adapter(self, adapter: MessageAdapter) -> None:
        """注册消息适配器"""
        self.adapters.append(adapter)

    async def start(self) -> None:
        """启动控制器"""
        # 检查控制器是否已经在运行
        if self.running:
            logger.warning("控制器已经在运行")
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
        
        logger.info("游戏控制器已启动")

    async def stop(self) -> None:
        """停止控制器"""
        # 如果控制器已经停止，直接返回
        if not self.running:
            return
            
        self.running = False
        
        # 停止所有适配器
        for adapter in self.adapters:
            await adapter.stop()
            
        # 停止Web状态检查器
        await self.web_inspector.stop()
            
        logger.info("游戏控制器已停止")
        
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
            logger.debug(f"处理事件: 类型={event.event_type}, 数据={event.data}")
            
            # 直接使用命令模式处理事件
            responses = await self._handle_event(event)
            
            # 处理响应
            for response in responses:
                if isinstance(response, GameEvent):
                    logger.debug(f"处理响应事件: 类型={response.event_type}")
                    await self._process_event(response)
                elif isinstance(response, dict) and "recipient" in response and "content" in response:
                    await self.send_message(response["recipient"], response["content"])
        except Exception as e:
            logger.exception(f"处理事件失败: {str(e)}")
            
    async def send_message(self, player_id: str, content: str) -> None:
        """发送消息给玩家"""
        logger.debug(f"发送消息给玩家: ID={player_id}, 内容前20字符='{content[:20]}...'")
        for adapter in self.adapters:
            await adapter.send_message(player_id, content)

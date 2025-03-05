import asyncio
import logging
import os
from typing import Optional, Dict, Any, List, Callable

from dingtalk_stream import DingTalkStreamClient, Credential, ChatbotMessage, AckMessage
from dingtalk_stream.chatbot import ChatbotHandler
from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent, PlayerRequestStartEvent
from adapters.command_handler import CommandHandler

logger = logging.getLogger(__name__)

class DingTalkHandler(ChatbotHandler):
    """钉钉消息处理器，符合SDK规范"""
    
    def __init__(self, callback_func: Callable):
        super().__init__()
        self.callback_func = callback_func
        self.reply_map: Dict[str, ChatbotMessage] = {}
        self.cmd_handler = CommandHandler()
        
        # 注册基本命令
        self.cmd_handler.register(
            "/加入游戏", ["/join"], 
            lambda pid, pname, args: PlayerJoinedEvent(pid, pname),
            "加入游戏"
        )
        self.cmd_handler.register(
            "/开始游戏", ["/start"], 
            lambda pid, pname, args: PlayerRequestStartEvent(pid, pname),
            "开始游戏"
        )
        # 注册帮助命令
        self.cmd_handler.register(
            "/help", ["/帮助"], 
            lambda pid, pname, args: None,  # 帮助命令不生成事件
            "显示帮助信息"
        )
        
    async def raw_process(self, callback: Any) -> AckMessage:
        """处理原始回调消息"""
        try:
            message = ChatbotMessage.from_dict(callback.data)
            await self.process(message)
            ack_message = AckMessage()
            ack_message.code = AckMessage.STATUS_OK
            return ack_message
        except Exception as e:
            logger.exception(f"处理钉钉消息失败: {str(e)}")
            ack_message = AckMessage()
            ack_message.code = AckMessage.STATUS_OK
            return ack_message # 即使处理失败也返回OK，避免重试
    
    async def process(self, message: ChatbotMessage) -> None:
        """处理钉钉消息"""
        try:
            text = message.text.content.strip()
            player_id = message.sender_staff_id
            player_name = message.sender_nick
            
            # 保存消息以便回复
            self.reply_map[player_id] = message
            
            # 解析为游戏事件
            event = None
            response = None
            
            if text.startswith('/'):
                # 使用命令处理器处理命令
                event, response = self.cmd_handler.process(text, player_id, player_name)
                
                # 特殊处理帮助命令
                if text == "/help" or text == "/帮助":
                    response = self.cmd_handler.get_help()
                
                # 如果有需要回复的消息
                if response:
                    self.reply_text(response, message)
            else:
                # 普通消息视为玩家行动
                event = PlayerActionEvent(player_id, text)
            
            # 调用回调处理事件
            if event:
                await self.callback_func(event)
                
        except Exception as e:
            logger.exception(f"处理钉钉消息失败: {str(e)}")

class DingTalkAdapter(MessageAdapter):
    """钉钉适配器"""
    
    def __init__(self, client_id: str = "", client_secret: str = ""):
        # 优先使用环境变量
        self.client_id = os.environ.get('DINGTALK_CLIENT_ID', '') or client_id
        self.client_secret = os.environ.get('DINGTALK_CLIENT_SECRET', '') or client_secret
        self.client = None
        self.handler = None
        self.event_queue = asyncio.Queue()
        self.running = False
        self._client_task = None
        
    async def start(self) -> None:
        """启动适配器"""
        if self.client:
            logger.warning("钉钉适配器已经启动")
            return
            
        # 创建凭证和客户端
        credential = Credential(self.client_id, self.client_secret)
        self.client = DingTalkStreamClient(credential)
        
        # 创建处理器
        self.handler = DingTalkHandler(self._on_message)
        
        # 注册消息处理器
        self.client.register_callback_handler(
            ChatbotMessage.TOPIC,
            self.handler
        )
        
        # 启动客户端
        self.running = True
        self._client_task = asyncio.create_task(self._run_client())
        logger.info("钉钉适配器已启动")
    
    async def _run_client(self) -> None:
        """运行钉钉客户端"""
        try:
            # 由于dingtalk_stream不支持异步，使用线程池执行
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.client.start_forever)
        except Exception as e:
            if self.running:
                logger.error(f"钉钉客户端异常: {str(e)}")
    
    async def stop(self) -> None:
        """停止适配器"""
        self.running = False
        
        # 取消客户端任务
        if self._client_task:
            self._client_task.cancel()
            try:
                await self._client_task
            except asyncio.CancelledError:
                pass
                
        # 重置客户端和处理器
        self.client = None
        self.handler = None
        logger.info("钉钉适配器已停止")
    
    async def _on_message(self, event: GameEvent) -> None:
        """处理消息回调"""
        await self.event_queue.put(event)
    
    async def receive_message(self) -> Optional[GameEvent]:
        """接收消息"""
        if not self.running:
            return None
            
        try:
            return await self.event_queue.get()
        except Exception as e:
            logger.error(f"接收消息失败: {str(e)}")
            return None
    
    async def send_message(self, player_id: str, content: str) -> None:
        """发送消息"""
        if not self.handler:
            logger.warning("钉钉处理器未初始化，无法发送消息")
            return
            
        if player_id not in self.handler.reply_map:
            logger.warning(f"找不到玩家消息: {player_id}")
            return
            
        message = self.handler.reply_map[player_id]
        self.handler.reply_text(content, message)

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable

from dingtalk_stream import DingTalkStreamClient, Credential, ChatbotMessage, AckMessage
from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent

logger = logging.getLogger(__name__)

class DingTalkHandler:
    """钉钉消息处理器"""
    
    def __init__(self, callback: Callable):
        self.callback = callback
        self.reply_map: Dict[str, ChatbotMessage] = {}
        
    async def process(self, callback: Any) -> tuple[str, str]:
        """处理钉钉消息"""
        try:
            # 解析消息
            message = ChatbotMessage.from_dict(callback.data)
            text = message.text.content.strip()
            player_id = message.sender_staff_id
            player_name = message.sender_nick
            
            # 保存消息以便回复
            self.reply_map[player_id] = message
            
            # 解析为游戏事件
            event = None
            if text.startswith('/'):
                if text == "/加入游戏" or text == "/join":
                    event = PlayerJoinedEvent(player_id, player_name)
                # 其他命令处理...
            else:
                # 普通消息视为玩家行动
                event = PlayerActionEvent(player_id, text)
            
            # 调用回调处理事件
            if event:
                await self.callback(event)
                
            return AckMessage.STATUS_OK, 'OK'
        except Exception as e:
            logger.exception(f"处理钉钉消息失败: {str(e)}")
            return AckMessage.STATUS_OK, 'ERROR'
    
    def reply_text(self, player_id: str, content: str) -> None:
        """回复文本消息"""
        if player_id not in self.reply_map:
            logger.warning(f"找不到玩家消息: {player_id}")
            return
            
        message = self.reply_map[player_id]
        message.reply_text(content)
        logger.debug(f"回复消息: {player_id}, {content}")

class DingTalkAdapter(MessageAdapter):
    """钉钉适配器"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client = None
        self.handler = None
        self.event_queue = asyncio.Queue()
        self.running = False
        
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
        asyncio.create_task(self._run_client())
        logger.info("钉钉适配器已启动")
    
    async def _run_client(self) -> None:
        """运行钉钉客户端"""
        while self.running:
            try:
                # 由于dingtalk_stream不支持异步，我们在单独的线程中运行
                self.client.start_forever()
            except Exception as e:
                logger.error(f"钉钉客户端异常: {str(e)}")
                if self.running:
                    await asyncio.sleep(10)  # 等待10秒后重试
    
    async def stop(self) -> None:
        """停止适配器"""
        self.running = False
        if self.client:
            # 没有优雅停止的方法，只能重置
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
            
        self.handler.reply_text(player_id, content)

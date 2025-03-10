import asyncio
import logging
import os
from typing import Optional, Dict, Any, List, Callable

from dingtalk_stream import DingTalkStreamClient, Credential, ChatbotMessage, AckMessage
from dingtalk_stream.frames import Headers
from dingtalk_stream.chatbot import ChatbotHandler
from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent, StartMatchEvent, EndMatchEvent, SetScenarioEvent, CreateRoomEvent, JoinRoomEvent, ListRoomsEvent, SelectCharacterEvent
from adapters.command_handler import CommandHandler

logger = logging.getLogger(__name__)

class DingTalkHandler(ChatbotHandler):
    """钉钉消息处理器，符合SDK规范"""
    
    def __init__(self, callback_func: Callable):
        super().__init__()
        self.callback_func = callback_func
        self.reply_map: Dict[str, ChatbotMessage] = {}
        self.cmd_handler = CommandHandler()
        
        # 系统命令已移除，所有游戏操作通过UI界面完成
        # 注册帮助命令
        self.cmd_handler.register(
            "/help", ["/帮助"], 
            lambda pid, pname, args: None,  # 帮助命令不生成事件
            "显示帮助信息 - 所有游戏操作现在通过UI界面完成，不再支持聊天命令"
        )
        
    # 删除自定义的raw_process方法，使用父类的实现
    
    async def process(self, message):
        """处理钉钉消息"""
        try:
            # 检查消息类型，如果是CallbackMessage，则转换为ChatbotMessage
            if hasattr(message, 'data') and not hasattr(message, 'text'):
                # 这是一个CallbackMessage，需要从data中提取信息并创建ChatbotMessage
                from dingtalk_stream.chatbot import ChatbotMessage
                chatbot_message = ChatbotMessage.from_dict(message.data)
                message = chatbot_message
            
            # 现在message应该是ChatbotMessage类型
            text = message.text.content.strip()
            player_id = message.sender_staff_id
            player_name = message.sender_nick
            message_id = message.message_id
            
            logger.info(f"收到钉钉消息: ID={message_id}, 玩家={player_name}({player_id}), 内容='{text}'")
            
            # 保存消息以便回复
            self.reply_map[player_id] = message
            
            # 解析为游戏事件
            event = None
            response = None
            
            if text.startswith('/'):
                # 使用命令处理器处理命令
                logger.info(f"处理命令: {text}, 玩家={player_name}({player_id})")
                event, response = self.cmd_handler.process(text, player_id, player_name)
                
                # 特殊处理帮助命令
                if text == "/help" or text == "/帮助":
                    response = self.cmd_handler.get_help()
                
                # 如果有需要回复的消息
                if response:
                    logger.info(f"命令处理响应: {response}")
                    self.reply_text(response, message)
            else:
                # 普通消息视为玩家行动
                logger.info(f"创建玩家行动事件: 玩家={player_name}({player_id}), 行动='{text}'")
                event = PlayerActionEvent(player_id, text)
            
            # 调用回调处理事件
            if event:
                logger.info(f"发送事件到游戏服务器: 类型={event.event_type}, 数据={event.data}")
                await self.callback_func(event)
                
            # 返回成功状态码和消息
            return AckMessage.STATUS_OK, "success"
        except Exception as e:
            logger.exception(f"处理钉钉消息失败: {str(e)}")
            # 即使处理失败也返回OK状态码，避免重试
            return AckMessage.STATUS_OK, f"处理异常但返回成功: {str(e)}"

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
        # 记录当前调用的来源以及参数
        import traceback
        call_stack = traceback.format_stack()
        logger.debug(f"发送消息调用栈: {call_stack}")
        logger.debug(f"发送消息参数: player_id={player_id}, content={content}")
        
        if not self.handler:
            logger.warning("钉钉处理器未初始化，无法发送消息")
            return
            
        if player_id not in self.handler.reply_map:
            # 输出更详细的信息用于调试
            logger.warning(f"找不到玩家消息: {player_id}")
            logger.debug(f"当前reply_map中的键: {list(self.handler.reply_map.keys())}")
            return
            
        message = self.handler.reply_map[player_id]
        self.handler.reply_text(content, message)

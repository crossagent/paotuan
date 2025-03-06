import asyncio
import logging
import json
from typing import Optional, Dict, Any, List, Callable, Set
import uuid

from adapters.base import MessageAdapter, GameEvent, PlayerJoinedEvent, PlayerActionEvent, PlayerRequestStartEvent, SetScenarioEvent, CreateRoomEvent, JoinRoomEvent, ListRoomsEvent, SelectCharacterEvent
from adapters.command_handler import CommandHandler

logger = logging.getLogger(__name__)

class WebAdapter(MessageAdapter):
    """Web适配器，用于处理Web客户端的消息"""
    
    def __init__(self):
        self.event_queue = asyncio.Queue()
        self.running = False
        self.connected_clients: Dict[str, "WebSocketConnection"] = {}  # player_id -> WebSocketConnection
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
        # 注册剧本命令
        self.cmd_handler.register(
            "/剧本", ["/scenario"], 
            lambda pid, pname, args: SetScenarioEvent(pid, args.strip()),
            "设置剧本（必须在游戏开始前），用法: /剧本 [剧本ID]"
        )
        # 注册选择角色命令
        self.cmd_handler.register(
            "/选角色", ["/select_character"], 
            lambda pid, pname, args: SelectCharacterEvent(pid, args.strip()),
            "选择角色（必须在游戏开始前），用法: /选角色 [角色名]"
        )
        # 注册房间相关命令
        self.cmd_handler.register(
            "/创建房间", ["/create_room"], 
            lambda pid, pname, args: CreateRoomEvent(pid, args.strip() or f"{pname}的房间"),
            "创建新房间，用法: /创建房间 [房间名称]"
        )
        self.cmd_handler.register(
            "/加入房间", ["/join_room"], 
            lambda pid, pname, args: JoinRoomEvent(pid, pname, args.strip()),
            "加入指定房间，用法: /加入房间 [房间ID]"
        )
        self.cmd_handler.register(
            "/房间列表", ["/list_rooms", "/rooms"], 
            lambda pid, pname, args: ListRoomsEvent(pid),
            "查看可用房间列表"
        )
        # 注册帮助命令
        self.cmd_handler.register(
            "/help", ["/帮助"], 
            lambda pid, pname, args: None,  # 帮助命令不生成事件
            "显示帮助信息"
        )
    
    async def start(self) -> None:
        """启动适配器"""
        if self.running:
            logger.warning("Web适配器已经启动")
            return
            
        self.running = True
        logger.info("Web适配器已启动")
    
    async def stop(self) -> None:
        """停止适配器"""
        self.running = False
        
        # 关闭所有WebSocket连接
        for client in list(self.connected_clients.values()):
            await client.close()
            
        self.connected_clients.clear()
        logger.info("Web适配器已停止")
    
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
        if not self.running:
            logger.warning("Web适配器未启动，无法发送消息")
            return
            
        if player_id not in self.connected_clients:
            logger.warning(f"找不到玩家连接: {player_id}")
            return
            
        client = self.connected_clients[player_id]
        await client.send_message(content)
    
    async def register_client(self, player_id: str, player_name: str, websocket) -> "WebSocketConnection":
        """注册WebSocket客户端"""
        if player_id in self.connected_clients:
            # 如果已存在连接，关闭旧连接
            old_connection = self.connected_clients[player_id]
            await old_connection.close()
            
        # 创建新连接
        connection = WebSocketConnection(player_id, player_name, websocket, self)
        self.connected_clients[player_id] = connection
        logger.info(f"注册WebSocket客户端: {player_name} (ID: {player_id})")
        return connection
    
    async def unregister_client(self, player_id: str) -> None:
        """注销WebSocket客户端"""
        if player_id in self.connected_clients:
            del self.connected_clients[player_id]
            logger.info(f"注销WebSocket客户端: {player_id}")
    
    async def handle_message(self, player_id: str, player_name: str, message: str) -> None:
        """处理从WebSocket接收到的消息"""
        try:
            logger.info(f"收到Web消息: 玩家={player_name}({player_id}), 内容='{message}'")
            
            # 解析为游戏事件
            event = None
            response = None
            
            if message.startswith('/'):
                # 使用命令处理器处理命令
                logger.info(f"处理命令: {message}, 玩家={player_name}({player_id})")
                event, response = self.cmd_handler.process(message, player_id, player_name)
                
                # 特殊处理帮助命令
                if message == "/help" or message == "/帮助":
                    response = self.cmd_handler.get_help()
                
                # 如果有需要回复的消息
                if response:
                    logger.info(f"命令处理响应: {response}")
                    await self.send_message(player_id, response)
            else:
                # 普通消息视为玩家行动
                logger.info(f"创建玩家行动事件: 玩家={player_name}({player_id}), 行动='{message}'")
                event = PlayerActionEvent(player_id, message)
            
            # 将事件放入队列
            if event:
                logger.info(f"发送事件到游戏服务器: 类型={event.event_type}, 数据={event.data}")
                await self.event_queue.put(event)
                
        except Exception as e:
            logger.exception(f"处理Web消息失败: {str(e)}")
            # 发送错误消息给客户端
            await self.send_message(player_id, f"处理消息失败: {str(e)}")

class WebSocketConnection:
    """WebSocket连接管理"""
    
    def __init__(self, player_id: str, player_name: str, websocket, adapter: WebAdapter):
        self.player_id = player_id
        self.player_name = player_name
        self.websocket = websocket
        self.adapter = adapter
        self.closed = False
    
    async def handle(self) -> None:
        """处理WebSocket连接"""
        try:
            # 发送欢迎消息
            await self.send_message(f"欢迎 {self.player_name}！输入 /help 查看可用命令。")
            
            # 处理消息
            while not self.closed:
                try:
                    # 使用receive_text()或receive_json()方法接收消息
                    message_type = await self.websocket.receive()
                    
                    if message_type["type"] == "websocket.disconnect":
                        logger.info(f"WebSocket客户端断开连接: {self.player_id}")
                        break
                        
                    if message_type["type"] == "websocket.receive":
                        if "text" in message_type:
                            # 文本消息
                            message = message_type["text"]
                            await self.adapter.handle_message(self.player_id, self.player_name, message)
                        elif "bytes" in message_type:
                            # 二进制消息，尝试解码为JSON
                            try:
                                data = json.loads(message_type["bytes"].decode('utf-8'))
                                if 'type' in data and 'content' in data:
                                    if data['type'] == 'message':
                                        await self.adapter.handle_message(self.player_id, self.player_name, data['content'])
                            except Exception as e:
                                logger.error(f"解析二进制消息失败: {str(e)}")
                                await self.send_message("消息格式错误")
                except Exception as e:
                    logger.error(f"接收WebSocket消息失败: {str(e)}")
                    if "Connection closed" in str(e):
                        break
        except Exception as e:
            logger.exception(f"WebSocket连接异常: {str(e)}")
        finally:
            # 关闭连接
            await self.close()
    
    async def send_message(self, content: str) -> None:
        """发送消息到WebSocket客户端"""
        if self.closed:
            return
            
        try:
            message = {
                "type": "message",
                "content": content
            }
            await self.websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {str(e)}")
            await self.close()
    
    async def close(self) -> None:
        """关闭WebSocket连接"""
        if self.closed:
            return
            
        self.closed = True
        await self.adapter.unregister_client(self.player_id)
        
        try:
            await self.websocket.close()
        except Exception as e:
            logger.error(f"关闭WebSocket连接失败: {str(e)}")

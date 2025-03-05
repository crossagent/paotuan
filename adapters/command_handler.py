import logging
from typing import Optional, Dict, Any, List, Callable, Tuple

from adapters.base import GameEvent

logger = logging.getLogger(__name__)

class CommandHandler:
    """命令处理器，统一管理聊天命令"""
    
    def __init__(self, default_response: str = "未识别的命令，请输入 /help 查看可用命令"):
        self.commands: Dict[str, Dict[str, Any]] = {}  # 命令映射表
        self.default_response: str = default_response
        
    def register(self, cmd_name: str, aliases: List[str], handler_func: Callable[[str, str, str], GameEvent], help_text: str = "") -> None:
        """
        注册一个命令及其别名
        
        Args:
            cmd_name: 命令名称
            aliases: 命令别名列表
            handler_func: 处理函数，接收 player_id, player_name, args 参数，返回 GameEvent
            help_text: 命令帮助文本
        """
        for name in [cmd_name] + aliases:
            self.commands[name] = {
                "handler": handler_func,
                "help": help_text
            }
            
    def process(self, text: str, player_id: str, player_name: str) -> Tuple[Optional[GameEvent], Optional[str]]:
        """
        处理命令文本，返回对应的事件和可能的回复
        
        Args:
            text: 命令文本
            player_id: 玩家ID
            player_name: 玩家名称
            
        Returns:
            Tuple[Optional[GameEvent], Optional[str]]: 事件和回复消息
        """
        if not text.startswith('/'):
            return None, None
            
        # 提取命令（支持带参数的命令，如 /roll 2d6）
        parts = text.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in self.commands:
            return self.commands[cmd]["handler"](player_id, player_name, args), None
        else:
            return None, self.default_response
            
    def get_help(self) -> str:
        """
        获取所有命令的帮助信息
        
        Returns:
            str: 帮助信息文本
        """
        help_text = "可用命令:\n"
        
        # 去重，避免别名重复显示
        unique_commands = {}
        for cmd, info in self.commands.items():
            if info["help"] not in unique_commands.values():
                unique_commands[cmd] = info["help"]
                
        for cmd, help_info in unique_commands.items():
            help_text += f"{cmd}: {help_info}\n"
            
        return help_text

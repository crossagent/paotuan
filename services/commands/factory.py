import logging
from typing import Dict, Any, Type

from core.game_state import GameState
from core.events import EventBus
from core.rules import RuleEngine
from services.commands.base import GameCommand, ServiceProvider
from services.commands.room_management_commands import CreateRoomCommand, JoinRoomCommand, ListRoomsCommand, LeaveRoomCommand
from services.commands.player_actions_commands import PlayerJoinedCommand, SelectCharacterCommand, CharacterActionCommand
from services.commands.match_flow_commands import StartMatchCommand, EndMatchCommand, SetScenarioCommand, PauseMatchCommand, ResumeMatchCommand
from services.commands.dm_operations_commands import DMNarrationCommand
from services.game_state_service import GameStateService
from services.room_service import RoomService
from services.match_service import MatchService
from services.turn_service import TurnService
from services.narration_service import NarrationService

logger = logging.getLogger(__name__)

class CommandServiceProvider(ServiceProvider):
    """命令服务提供者，实现ServiceProvider接口"""
    
    def __init__(self, game_state: GameState, event_bus: EventBus, 
                 ai_service: Any, rule_engine: RuleEngine):
        """初始化服务提供者
        
        Args:
            game_state: GameState - 游戏状态
            event_bus: EventBus - 事件总线
            ai_service: Any - AI服务
            rule_engine: RuleEngine - 规则引擎
        """
        self.game_state = game_state
        self.event_bus = event_bus
        self.ai_service = ai_service
        self.rule_engine = rule_engine
        self._services = {}
        
    def get_service(self, service_type: Type) -> Any:
        """获取指定类型的服务实例
        
        Args:
            service_type: Type - 服务类型
            
        Returns:
            Any: 服务实例
        """
        # 如果服务已经创建，直接返回
        if service_type in self._services:
            return self._services[service_type]
        
        # 根据服务类型创建对应的服务实例
        if service_type == GameStateService:
            service = GameStateService(self.game_state, self.event_bus)
        elif service_type == RoomService:
            service = RoomService(self.game_state, self.event_bus)
        elif service_type == MatchService:
            service = MatchService(self.game_state, self.event_bus)
        elif service_type == TurnService:
            service = TurnService(self.rule_engine)
        elif service_type == NarrationService:
            service = NarrationService(self.ai_service, self.rule_engine)
        else:
            raise ValueError(f"未知服务类型: {service_type}")
        
        # 缓存服务实例
        self._services[service_type] = service
        return service

class CommandFactory:
    """命令工厂，用于创建命令对象"""
    
    def __init__(self, game_state: GameState, event_bus: EventBus, 
                 ai_service: Any, rule_engine: RuleEngine):
        """初始化命令工厂
        
        Args:
            game_state: GameState - 游戏状态
            event_bus: EventBus - 事件总线
            ai_service: Any - AI服务
            rule_engine: RuleEngine - 规则引擎
        """
        self.service_provider = CommandServiceProvider(
            game_state, event_bus, ai_service, rule_engine
        )
        
    def create_command(self, event_type: str) -> GameCommand:
        """根据事件类型创建对应的命令对象
        
        Args:
            event_type: str - 事件类型
            
        Returns:
            GameCommand: 命令对象
            
        Raises:
            ValueError: 当事件类型未知时抛出
        """
        # 房间管理命令
        if event_type == "CREATE_ROOM":
            return CreateRoomCommand(self.service_provider)
        elif event_type == "JOIN_ROOM":
            return JoinRoomCommand(self.service_provider)
        elif event_type == "LIST_ROOMS":
            return ListRoomsCommand(self.service_provider)
        elif event_type == "PLAYER_LEFT":
            return LeaveRoomCommand(self.service_provider)
        
        # 玩家操作命令
        elif event_type == "PLAYER_JOINED":
            return PlayerJoinedCommand(self.service_provider)
        elif event_type == "PLAYER_ACTION":
            return CharacterActionCommand(self.service_provider)
        elif event_type == "SELECT_CHARACTER":
            return SelectCharacterCommand(self.service_provider)
        
        # 游戏流程命令
        elif event_type == "START_MATCH":
            return StartMatchCommand(self.service_provider)
        elif event_type == "END_MATCH":
            return EndMatchCommand(self.service_provider)
        elif event_type == "SET_SCENARIO":
            return SetScenarioCommand(self.service_provider)
        elif event_type == "PAUSE_MATCH":
            return PauseMatchCommand(self.service_provider)
        elif event_type == "RESUME_MATCH":
            return ResumeMatchCommand(self.service_provider)
        
        # DM操作命令
        elif event_type == "DM_NARRATION":
            return DMNarrationCommand(self.service_provider)
        else:
            raise ValueError(f"未知事件类型: {event_type}")

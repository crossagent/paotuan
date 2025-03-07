import logging
from typing import Dict, Any

from core.game import GameInstance
from core.events import EventBus
from core.rules import RuleEngine
from services.commands.base import GameCommand
from services.commands.room_commands import CreateRoomCommand, JoinRoomCommand, ListRoomsCommand
from services.commands.player_commands import PlayerJoinedCommand, SelectCharacterCommand, PlayerLeftCommand
from services.commands.game_commands import StartMatchCommand, EndMatchCommand, SetScenarioCommand, DMNarrationCommand, CharacterActionCommand

logger = logging.getLogger(__name__)

class CommandFactory:
    """命令工厂，用于创建命令对象"""
    
    def __init__(self, game_instance: GameInstance, event_bus: EventBus, 
                 ai_service: Any, rule_engine: RuleEngine):
        self.game_instance = game_instance
        self.event_bus = event_bus
        self.ai_service = ai_service
        self.rule_engine = rule_engine
        
    def create_command(self, event_type: str) -> GameCommand:
        """根据事件类型创建对应的命令对象"""
        # 玩家相关命令
        if event_type == "PLAYER_JOINED":
            return PlayerJoinedCommand(self.game_instance, self.event_bus, 
                                      self.ai_service, self.rule_engine)
        elif event_type == "PLAYER_ACTION":
            return CharacterActionCommand(self.game_instance, self.event_bus, 
                                         self.ai_service, self.rule_engine)
        elif event_type == "SELECT_CHARACTER":
            return SelectCharacterCommand(self.game_instance, self.event_bus, 
                                         self.ai_service, self.rule_engine)
        
        # 游戏相关命令
        elif event_type == "START_MATCH":
            return StartMatchCommand(self.game_instance, self.event_bus, 
                                   self.ai_service, self.rule_engine)
        elif event_type == "END_MATCH":
            return EndMatchCommand(self.game_instance, self.event_bus, 
                                  self.ai_service, self.rule_engine)
        elif event_type == "SET_SCENARIO":
            return SetScenarioCommand(self.game_instance, self.event_bus, 
                                     self.ai_service, self.rule_engine)
        elif event_type == "DM_NARRATION":
            return DMNarrationCommand(self.game_instance, self.event_bus, 
                                     self.ai_service, self.rule_engine)
        
        # 房间相关命令
        elif event_type == "CREATE_ROOM":
            return CreateRoomCommand(self.game_instance, self.event_bus, 
                                    self.ai_service, self.rule_engine)
        elif event_type == "JOIN_ROOM":
            return JoinRoomCommand(self.game_instance, self.event_bus, 
                                  self.ai_service, self.rule_engine)
        elif event_type == "LIST_ROOMS":
            return ListRoomsCommand(self.game_instance, self.event_bus, 
                                   self.ai_service, self.rule_engine)
        elif event_type == "PLAYER_LEFT":
            return PlayerLeftCommand(self.game_instance, self.event_bus,
                                    self.ai_service, self.rule_engine)
        else:
            raise ValueError(f"未知事件类型: {event_type}")

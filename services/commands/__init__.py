# 导出基类
from services.commands.base import GameCommand

# 导出房间相关命令
from services.commands.room_commands import (
    CreateRoomCommand,
    JoinRoomCommand,
    ListRoomsCommand
)

# 导出玩家相关命令
from services.commands.player_commands import (
    PlayerJoinedCommand,
    PlayerActionCommand,
    SelectCharacterCommand
)

# 导出游戏相关命令
from services.commands.game_commands import (
    StartGameCommand,
    SetScenarioCommand,
    DMNarrationCommand
)

# 导出命令工厂
from services.commands.factory import CommandFactory

# 为了向后兼容，导出所有命令类
__all__ = [
    'GameCommand',
    'CreateRoomCommand',
    'JoinRoomCommand',
    'ListRoomsCommand',
    'PlayerJoinedCommand',
    'PlayerActionCommand',
    'SelectCharacterCommand',
    'StartGameCommand',
    'SetScenarioCommand',
    'DMNarrationCommand',
    'CommandFactory'
]

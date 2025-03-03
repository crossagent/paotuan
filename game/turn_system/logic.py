from ..state.models import Match, Room, Turn, TurnType, Player
from typing import Optional, List, Dict, Any
import logging
from .base_handler import TurnHandler
from .dm_turn import DMTurnHandler
from .player_turn import PlayerTurnHandler  # 新增导入

logger = logging.getLogger(__name__)

class GameMatchLogic:
    def __init__(self) -> None:
        self.current_room: Optional[Room] = None
        self.handlers: List[TurnHandler] = []
        self.players: List[Player] = []  # 管理玩家列表
        self.message_callback = None  # 新增：消息回调函数
        
        # 初始化并添加回合处理器
        self.add_handler(DMTurnHandler())
        self.add_handler(PlayerTurnHandler())

    def set_message_callback(self, callback) -> None:
        """设置消息回调函数，用于向钉钉发送消息"""
        self.message_callback = callback

    def add_handler(self, handler: TurnHandler) -> None:
        self.handlers.append(handler)

    # ===== 从Room类移出的方法 =====
    def create_room(self, room_id: str) -> None:
        """创建新房间"""
        if self.current_room:
            raise InvalidGameOperation("已有活跃房间")
        self.current_room = Room(room_id=room_id)
        logger.info(f"房间已创建：{room_id}")

    def create_new_match(self, room: Room, scene: str) -> None:
        """为房间创建新比赛"""
        new_match = Match(match_id=len(room.history) + 1, scene=scene)
        room.history.append(new_match)
        room.current_match = new_match
        logger.info(f"开始新游戏局，场景：{scene} 房间ID：{room.room_id}")

    def add_player(self, player_id: str, player_name: str) -> None:
        """向当前房间添加玩家，只能在创建房间后、开始比赛前添加"""
        if not self.current_room:
            raise InvalidGameOperation("请先创建房间")
        
        # 检查是否已经开始比赛
        if self.current_room.current_match:
            raise InvalidGameOperation("游戏已经开始，无法加入新玩家")
            
        # 检查玩家是否已经在房间中
        for existing_player in self.current_room.players:
            if existing_player.id == player_id:
                logger.info(f"玩家已在房间中：{player_id}")
                return
                
        # 创建新玩家并添加到房间
        new_player = Player(id=player_id, name=player_name)
        self.current_room.players.append(new_player)
        
        logger.info(f"玩家{player_name}(ID:{player_id})加入房间")
        
        # 通知玩家已加入
        if self.message_callback:
            self.message_callback(player_id, f"你已成功加入房间：{self.current_room.room_id}")

    # ===== 从Match类移出的方法 =====
    def start_new_turn(self, match: Match, turn_type: TurnType) -> Turn:
        """开始新回合"""
        new_turn = Turn(turn_id=len(match.turns) + 1, turn_type=turn_type)
        match.turns.append(new_turn)
        match.current_turn = new_turn
        logger.debug(f"开始新回合，类型：{turn_type} 回合ID：{new_turn.turn_id}")
        
        # 通知处理器新回合开始
        if self.current_room:
            for handler in self.handlers:
                handler.on_enter_turn(new_turn, self.current_room.players, match)
                
        return new_turn

    def end_current_turn(self, match: Match) -> None:
        """结束当前回合"""
        if match.current_turn and match.current_turn.is_completed():
            # 通知处理器回合结束
            for handler in self.handlers:
                handler.on_finish_turn()
                
            logger.info(f"结束当前回合，回合ID：{len(match.turns)}")
            match.current_turn = None

    def handle_turn_transition(self) -> Optional[str]:
        """处理回合状态转换"""
        if not self.current_room or not self.current_room.current_match:
            logger.warning("当前没有正在进行的比赛")
            return None
            
        current_match = self.current_room.current_match
        
        # 检查当前回合是否已完成
        if current_match.current_turn and current_match.current_turn.is_completed():
            # 获取当前回合和下一个回合的信息
            current_turn = current_match.current_turn
            next_turn_info = current_turn.next_turn_info
            
            # 结束当前回合
            self.end_current_turn(current_match)
            
            # 创建下一个回合
            if 'turn_type' in next_turn_info:
                new_turn = self.start_new_turn(current_match, next_turn_info['turn_type'])
                
                # 设置激活玩家（如果有）
                if 'active_players' in next_turn_info:
                    new_turn.active_players = next_turn_info['active_players']
                
                logger.info(f"回合转换成功，新回合类型：{next_turn_info['turn_type']}，激活玩家：{new_turn.active_players}")
                
                # 通知玩家
                self._notify_players_of_next_turn()
                return "回合转换成功"
            else:
                logger.warning("未指定下一个回合类型")
                return None
        else:
            logger.warning("回合转换条件未满足")
            return None

    # ===== 从Turn类移出的方法 =====
    # 这些方法已移动到对应的TurnHandler类中

    # ===== 新增方法 =====
    def start_game(self, scene: str) -> None:
        """使用当前房间中的玩家开始新游戏"""
        if not self.current_room:
            raise InvalidGameOperation("请先创建房间")
        if self.current_room.current_match:
            raise InvalidGameOperation("当前已有进行中的比赛")
        if not self.current_room.players:
            raise InvalidGameOperation("房间中没有玩家，无法开始游戏")
            
        # 创建新比赛
        self.create_new_match(self.current_room, scene)
            
        # 直接开始一个DM回合
        if self.current_room.current_match:
            # 创建DM回合
            self.start_new_turn(self.current_room.current_match, TurnType.DM)
            logger.info("比赛开始，创建初始DM回合")
            
            # 通知所有玩家游戏开始
            for player in self.current_room.players:
                self.reply_to_player(player.id, f"游戏已开始，当前场景为：{scene}")
                
        logger.info(f"比赛开始 场景：{scene} 玩家数：{len(self.current_room.players)}")

    # ===== 原有方法修改 =====
    def destroy_room(self) -> None:
        """销毁当前房间"""
        if self.current_room and self.current_room.current_match:
            self.end_match()
        self.current_room = None
        logger.info("房间已销毁")

    def end_match(self) -> None:
        """结束当前比赛"""
        if not self.current_room or not self.current_room.current_match:
            raise InvalidGameOperation("没有进行中的比赛")
            
        self.current_room.current_match = None
        logger.info("比赛已结束")

    def process_event(self, event: Dict[str, Any]) -> Optional[str]:
        """统一处理游戏事件"""
        # 分发事件到各个处理器
        for handler in self.handlers:
            handler.handle_event(event)
            
        # 检查当前回合是否已完成，如果已完成则执行回合转换
        current_turn = self.get_current_turn()
        if current_turn and current_turn.is_completed():
            return self.handle_turn_transition()
            
        return None

    def _notify_players_of_next_turn(self) -> None:
        """通知所有玩家进入下一轮"""
        next_turn = self.get_current_turn()
        if next_turn and next_turn.turn_type == TurnType.PLAYER:
            # 发送消息给所有玩家，告知他们新的玩家回合开始
            for player in self.current_room.players:
                self.reply_to_player(player.id, "新的玩家回合已开始，请提交你的行动")

    def reply_to_player(self, player_id: str, message: str) -> None:
        """发送消息给指定玩家"""
        logger.info(f"回复玩家 {player_id}: {message}")
        # 使用回调函数发送消息
        if self.message_callback:
            self.message_callback(player_id, message)
        else:
            logger.warning("消息回调未设置，无法发送消息")

    def get_current_turn(self) -> Optional[Turn]:
        """获取当前回合"""
        if self.current_room and self.current_room.current_match:
            return self.current_room.current_match.current_turn
        return None

# 异常类
class PlayerTimeoutError(Exception):
    """玩家操作超时异常"""

class InvalidGameOperation(Exception):
    """非法游戏操作异常"""

from game.turn_system.base_handler import TurnHandler
from game.state.models import TurnType, Player, InvalidTurnOperation, TurnStatus
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class PlayerTurnHandler(TurnHandler):
    def __init__(self) -> None:
        super().__init__()

    def handle_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get('type')
        
        if event_type == 'player_action':
            player_id = event.get('player_id')
            action = event.get('content')  # 统一使用content字段
            
            if not self.current_turn:
                logger.error("当前回合未初始化")
                return
            
            try:
                # 直接处理玩家行动
                self.process_player_action(player_id, action)
            except InvalidTurnOperation as e:
                logger.error(f"非法操作: {str(e)}")
    
    def process_player_action(self, player_id: str, action: str) -> None:
        """处理玩家行动（仅限玩家回合）"""
        if not self.current_turn:
            logger.error("当前回合未初始化")
            return
            
        if self.current_turn.turn_type != TurnType.PLAYER:
            raise InvalidTurnOperation("非玩家回合不能处理玩家行动")
            
        if player_id not in self.current_turn.active_players:
            raise InvalidTurnOperation("当前玩家不在激活列表中")
            
        self.current_turn.actions[player_id] = action
        logger.info(f"玩家{player_id}提交动作：{action}")
        
        # 仅在全部提交时标记完成
        if self.all_players_submitted():
            self.current_turn.status = TurnStatus.COMPLETED
            logger.info(f"玩家回合{self.current_turn.turn_id}已完成所有提交")
    
    def all_players_submitted(self) -> bool:
        """检查所有玩家提交（仅限玩家回合）"""
        if not self.current_turn:
            return False
            
        return self.current_turn.turn_type == TurnType.PLAYER and \
               set(self.current_turn.actions.keys()) == set(self.current_turn.active_players)

# 示例使用
if __name__ == "__main__":
    from game.turn_system.logic import GameMatchLogic
    
    game_logic = GameMatchLogic()
    game_logic.create_room("test_room")
    player1 = Player(name="Alice", id="alice_id")
    
    handler = PlayerTurnHandler()
    game_logic.add_handler(handler)
    
    # 开始比赛
    game_logic.start_match("初始场景", [player1])
    
    # 模拟玩家行动
    event = {
        'type': 'player_action',
        'player_id': 'alice_id',
        'content': '探索前方的道路'
    }
    
    handler.handle_event(event)
    print("当前回合状态:", "已完成" if handler.current_turn and handler.current_turn.is_completed() else "未完成")

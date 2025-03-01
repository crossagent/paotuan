from game.turn_system.base_handler import TurnHandler
from game.turn_system.logic import GameMatchLogic
from game.state.models import TurnType, Player, InvalidTurnOperation
from typing import List
import logging

logger = logging.getLogger(__name__)

class PlayerTurnHandler(TurnHandler):
    def __init__(self, game_logic: GameMatchLogic):
        super().__init__(game_logic)

    def handle_event(self, event: dict) -> bool:
        if event.get('type') != 'player_action':
            return False
            
        player_id = event.get('player_id')
        action = event.get('action')
        current_turn = self.game_logic.current_room.current_match.current_turn
        
        try:
            current_turn.process_player_action(player_id, action)
            # 检查是否所有玩家已提交
            if current_turn.all_players_submitted():
                self.set_needs_transition(True)
                return True
        except InvalidTurnOperation as e:
            logger.error(f"非法操作: {str(e)}")
            
        return False

# 示例使用
if __name__ == "__main__":
    game_logic = GameMatchLogic()
    game_logic.start_new_round("初始场景")
    player1 = Player(name="Alice")
    game_logic.current_room.add_player(player1)
    handler = PlayerTurnHandler(game_logic)
    game_logic.add_handler(handler)
    handler.start_turn(["Alice"])
    new_state = handler.submit_action("Alice", "探索前方的道路")
    print("更新后的游戏状态:", new_state)
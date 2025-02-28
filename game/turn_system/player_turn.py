from game.turn_system.base_handler import TurnHandler
from game.turn_system.logic import GameMatch, TurnType, Player, InvalidTurnOperation
from typing import List  # 添加此行以导入List类型

class PlayerTurnHandler(TurnHandler):
    def __init__(self, game_logic: GameMatch):
        super().__init__(game_logic)

    def start_turn(self, players: List[str]):
        """初始化玩家回合"""
        if not self.game_logic.current_room or not self.game_logic.current_room.current_match:
            raise InvalidTurnOperation("当前没有正在进行的游戏局")
        
        current_match = self.game_logic.current_room.current_match
        current_match.start_new_turn(TurnType.PLAYER)
        current_match.current_turn.active_players = players

    def submit_action(self, player_id: str, action: str) -> str:
        """处理单个玩家提交"""
        current_turn = self.game_logic.current_room.current_match.current_turn
        
        if player_id not in current_turn.active_players:
            return "当前回合无需行动"
        
        if player_id in current_turn.actions:
            return "已提交过动作，请等待"

        current_turn.process_player_action(player_id, action)

        if current_turn.is_completed():
            self.set_needs_transition(True)
            return "所有玩家已行动，等待状态转换"
        return f"玩家{player_id}已行动：{action}"

    def update(self):
        """更新玩家回合状态"""
        if self.needs_transition:
            self.game_logic.handle_turn_transition()
            self.set_needs_transition(False)

# 示例使用
if __name__ == "__main__":
    game_logic = GameMatch()
    game_logic.start_new_round("初始场景")
    player1 = Player(name="Alice")
    game_logic.current_room.add_player(player1)
    handler = PlayerTurnHandler(game_logic)
    game_logic.add_handler(handler)
    handler.start_turn(["Alice"])
    new_state = handler.submit_action("Alice", "探索前方的道路")
    print("更新后的游戏状态:", new_state)

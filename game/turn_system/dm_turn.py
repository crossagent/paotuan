from ai.chains.story_gen import TurnProcessingChain
from game.turn_system.base_handler import TurnHandler
from game.turn_system.logic import GameMatchLogic
from game.state.models import TurnType, Player
from typing import List

class DMTurnHandler(TurnHandler):
    def __init__(self, game_logic: GameMatchLogic):
        super().__init__(game_logic)

    def handle_event(self, event: dict) -> bool:
        if event.get('type') != 'dm_narration':
            return False
            
        narration = event.get('content')
        current_turn = self.game_logic.current_room.current_match.current_turn
        current_turn.process_dm_turn(narration)
        
        # DM叙事完成后立即触发转换
        self.set_needs_transition(True)
        return True

    def generate_narration(self) -> str:
        """生成并应用剧情叙述"""
        current_match = self.game_logic.current_room.current_match
        players = [p.name for p in self.game_logic.current_room.players]

        result = TurnProcessingChain().process_dm_turn(current_match, players)
        current_match.current_turn.process_dm_turn(result["narration"])
        
        self.set_needs_transition(True)
        return result["narration"]

    def update(self):
        """更新DM回合状态"""
        if self.needs_transition:
            self.game_logic.handle_turn_transition()
            self.set_needs_transition(False)

    def activate_players(self, players: List[str]):
        """设置下一回合激活玩家"""
        current_match = self.game_logic.current_room.current_match
        current_match.start_new_turn(TurnType.PLAYER)
        current_match.current_turn.active_players = players

# 示例使用
if __name__ == "__main__":
    game_logic = GameMatchLogic()
    game_logic.start_new_round("初始场景")
    player1 = Player(name="Alice")
    player2 = Player(name="Bob")
    game_logic.current_room.add_player(player1)
    game_logic.current_room.add_player(player2)
    
    handler = DMTurnHandler(game_logic)
    game_logic.add_handler(handler)
    narration = handler.generate_narration()
    print("DM生成的剧情:", narration)
    
    # 激活下一轮玩家
    handler.activate_players(["Alice", "Bob"])
    print("已激活玩家：", handler.game_logic.current_room.current_match.current_turn.active_players)

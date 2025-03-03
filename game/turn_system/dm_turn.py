from ai.chains.story_gen import TurnProcessingChain
from game.turn_system.base_handler import TurnHandler
from game.state.models import TurnType, Player, TurnStatus, InvalidTurnOperation
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DMTurnHandler(TurnHandler):
    def __init__(self) -> None:
        super().__init__()

    def handle_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get('type')
        
        if event_type == 'dm_narration':
            narration = event.get('content')
            
            if not self.current_turn:
                logger.error("当前回合未初始化")
                return
                
            self.process_dm_turn(narration)
    
    def process_dm_turn(self, narration: str) -> None:
        """处理DM叙事（仅限DM回合）"""
        if not self.current_turn:
            logger.error("当前回合未初始化")
            return
            
        if self.current_turn.turn_type != TurnType.DM:
            raise InvalidTurnOperation("非DM回合不能处理叙事")
            
        self.current_turn.actions["dm_narration"] = narration
        self.current_turn.status = TurnStatus.COMPLETED

    def generate_narration(self) -> str:
        """生成并应用剧情叙述"""
        if not self.current_turn or 'match' not in self.context:
            logger.error("当前回合或比赛上下文未初始化")
            return "错误：回合未初始化"
            
        current_match = self.context['match']
        players = [p.name for p in self.context.get('players', [])]

        result = TurnProcessingChain().process_dm_turn(current_match, players)
        self.process_dm_turn(result["narration"])
        
        return result["narration"]

    def request_next_player_turn(self, players: List[str]) -> None:
        """请求下一个玩家回合并设置激活玩家"""
        if not self.current_turn:
            logger.error("当前回合未初始化")
            return
            
        # 只设置状态，不直接调用game_logic
        self.current_turn.status = TurnStatus.COMPLETED
        # 在context中存储下一回合需要激活的玩家
        self.context['next_active_players'] = players
        logger.info(f"DM回合完成，请求下一回合激活玩家: {players}")

# 示例使用
if __name__ == "__main__":
    from game.turn_system.logic import GameMatchLogic
    
    game_logic = GameMatchLogic()
    game_logic.create_room("test_room")
    player1 = Player(name="Alice", id="alice_id")
    player2 = Player(name="Bob", id="bob_id")
    
    handler = DMTurnHandler()
    game_logic.add_handler(handler)
    
    # 开始比赛
    game_logic.start_match("初始场景", [player1, player2])
    
    # 生成DM叙述
    narration = handler.generate_narration()
    print("DM生成的剧情:", narration)
    
    # 请求下一轮玩家回合
    handler.request_next_player_turn(["alice_id", "bob_id"])
    print("已请求激活玩家：", handler.context.get('next_active_players', []))

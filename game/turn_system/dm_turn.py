from ai.chains.story_gen import TurnProcessingChain
from game.turn_system.base_handler import TurnHandler
from game.state.models import TurnType, Player, TurnStatus, InvalidTurnOperation, EventType
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DMTurnHandler(TurnHandler):
    # 明确声明关注的事件类型
    event_types: List[str] = [EventType.DM_NARRATION]
    
    def __init__(self) -> None:
        super().__init__()

    def _process_event(self, event: Dict[str, Any]) -> None:
        """处理DM相关事件"""
        event_type = event.get('type')
        
        if event_type == EventType.DM_NARRATION:
            narration = event.get('content')
            
            current_turn = self.get_current_turn()
            if not current_turn:
                logger.error("当前回合未初始化")
                return
                
            self.process_dm_turn(narration)
    
    def process_dm_turn(self, narration: str) -> None:
        """处理DM叙事（仅限DM回合）"""
        current_turn = self.get_current_turn()
        if not current_turn:
            logger.error("当前回合未初始化")
            return
            
        if current_turn.turn_type != TurnType.DM:
            raise InvalidTurnOperation("非DM回合不能处理叙事")
            
        current_turn.actions["dm_narration"] = narration
        current_turn.status = TurnStatus.COMPLETED

    def generate_narration(self) -> str:
        """生成并应用剧情叙述"""
        current_turn = self.get_current_turn()
        if not current_turn or 'match' not in self.context:
            logger.error("当前回合或比赛上下文未初始化")
            return "错误：回合未初始化"
            
        current_match = self.context['match']
        players = [p.name for p in self.context.get('players', [])]

        result = TurnProcessingChain().process_dm_turn(current_match, players)
        self.process_dm_turn(result["narration"])
        
        return result["narration"]
        
    def on_finish_turn(self) -> None:
        """DM回合结束时，设置下一个回合的信息"""
        # 清理资源，执行回合结束时的操作
        super().on_finish_turn()
        
        current_turn = self.get_current_turn()
        if not current_turn:
            logger.error("当前回合未初始化")
            return
        
        # 设置下一个回合的类型为玩家回合
        current_turn.next_turn_info['turn_type'] = TurnType.PLAYER
        
        logger.info("DM回合结束，下一回合为玩家回合")

    def request_next_player_turn(self, players: List[str]) -> None:
        """请求下一个玩家回合并设置激活玩家"""
        current_turn = self.get_current_turn()
        if not current_turn:
            logger.error("当前回合未初始化")
            return
            
        # 设置回合状态为完成
        current_turn.status = TurnStatus.COMPLETED
        
        # 在next_turn_info中设置下一回合的类型和激活玩家
        current_turn.next_turn_info['turn_type'] = TurnType.PLAYER
        current_turn.next_turn_info['active_players'] = players
        
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
    current_turn = handler.get_current_turn()
    print("已请求激活玩家：", current_turn.next_turn_info.get('active_players', []))

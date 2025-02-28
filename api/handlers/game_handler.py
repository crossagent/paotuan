import logging
from dingtalk_stream import ChatbotHandler, AckMessage, ChatbotMessage
from game.turn_system.logic import GameMatchLogic
from ai.chains.story_gen import LLMTimeoutError, PlayerTimeoutError

class GameMessageHandler(ChatbotHandler):
    def __init__(self, game_match: GameMatchLogic, logger: logging.Logger = None):
        super().__init__()
        self.game_match = game_match  # 引用游戏状态
        self.logger = logger if logger else logging.getLogger(__name__)

    def reply_to_player(self, player_id: str, message: str):
        """向指定玩家发送消息"""
        # 实现具体的发送逻辑（例如通过钉钉API）
        self.logger.info(f"回复玩家 {player_id}: {message}")
        # 这里可以添加实际的发送逻辑代码

    async def process(self, callback):
        incoming_message = ChatbotMessage.from_dict(callback.data)
        text = incoming_message.text.content.strip()
        player_id = incoming_message.sender_staff_id

        self.logger.info(f"接收到玩家输入：玩家ID：{player_id} 输入内容：{text}")

        try:
            if text == "/开始游戏":
                if not self.game_match.current_room or not self.game_match.current_room.current_match:
                    self.game_match.start_match(scene="初始场景", players=[])
                    response_text = "游戏已开始，当前场景为：初始场景"
                else:
                    response_text = "当前已有进行中的游戏局，请等待当前游戏结束。"
            else:
                # 创建事件对象并传递给GameMatch
                event = {
                    'type': 'player_action' if text.startswith('/') else 'dm_narration',
                    'player_id': player_id,
                    'content': text
                }
                try:
                    response_text = self.game_match.process_event(event)
                    self.logger.info(f"处理玩家行动：玩家ID：{player_id} 行动内容：{text} 响应：{response_text}")
                    
                    # 通过GameMatch统一管理状态转换

                except LLMTimeoutError:
                    response_text = "大模型请求超时，请稍后再试"
                    self.logger.warning(f"大模型请求超时：玩家ID：{player_id} 行动内容：{text}")
                except PlayerTimeoutError:
                    response_text = "玩家输入超时，跳过本轮"
                    self.logger.warning(f"玩家输入超时：玩家ID：{player_id} 行动内容：{text}")
        except Exception as e:
            self.logger.error(f"处理玩家行动时出错: {str(e)}", exc_info=True)
            response_text = "游戏系统出现错误，请联系管理员"

        # 回复钉钉消息
        self.reply_to_player(player_id, response_text)
        return AckMessage.STATUS_OK, 'OK'

if __name__ == "__main__":
    handler = GameMessageHandler(None, logging.getLogger())
    print("GameMessageHandler测试运行")

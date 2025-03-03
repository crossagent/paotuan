import logging
from dingtalk_stream import ChatbotHandler, AckMessage, ChatbotMessage
from game.turn_system.logic import GameMatchLogic, InvalidGameOperation
from ai.chains.story_gen import LLMTimeoutError, PlayerTimeoutError
from game.state.models import EventType

class GameMessageHandler(ChatbotHandler):
    def __init__(self, game_match: GameMatchLogic, logger: logging.Logger = None) -> None:
        super().__init__()
        self.game_match = game_match  # 引用游戏状态
        self.logger = logger if logger else logging.getLogger(__name__)
        
        # 添加玩家消息映射字典
        self.player_messages = {}
        
        # 设置消息回调，让 GameMatchLogic 可以主动发送消息
        self.game_match.set_message_callback(self.reply_to_player)
    
    def reply_to_player(self, player_id: str, message: str) -> None:
        """通过玩家ID发送消息"""
        if player_id in self.player_messages:
            incoming_message = self.player_messages[player_id]
            self.reply_text(message, incoming_message)
            self.logger.info(f"通过ID回复玩家 {player_id}: {message}")
        else:
            self.logger.warning(f"无法回复玩家 {player_id}，找不到对应的消息上下文")

    async def process(self, callback: any) -> tuple[str, str]:
        incoming_message = ChatbotMessage.from_dict(callback.data)
        text = incoming_message.text.content.strip()
        player_id = incoming_message.sender_staff_id
        player_name = incoming_message.sender_nick  # 获取玩家昵称

        # 保存玩家最新消息
        self.player_messages[player_id] = incoming_message

        self.logger.info(f"接收到玩家输入：玩家ID：{player_id} 输入内容：{text}")

        try:
            # 处理加入游戏指令
            if text == "/加入游戏" or text == "/join":
                try:
                    self.game_match.add_player(player_id, player_name)
                    response_text = f"你已成功加入游戏，当前玩家数：{len(self.game_match.current_room.players) if self.game_match.current_room else 0}"
                except InvalidGameOperation as e:
                    response_text = f"加入游戏失败：{str(e)}"
                    self.logger.warning(f"玩家加入游戏失败: {str(e)}")
                except Exception as e:
                    response_text = "加入游戏失败：系统错误."
                    self.logger.error(f"玩家加入游戏失败: {str(e)}", exc_info=True)
                
            # 处理开始游戏指令
            elif text == "/开始游戏" or text == "/start":
                if not self.game_match.current_room:
                    response_text = "请先创建房间"
                elif not self.game_match.current_room.players:
                    response_text = "房间中没有玩家，请先加入游戏"
                elif self.game_match.current_room.current_match:
                    response_text = "当前已有进行中的游戏局，请等待当前游戏结束。"
                else:
                    try:
                        self.game_match.start_game(scene="初始场景")
                        response_text = "游戏已开始，当前场景为：初始场景"
                    except Exception as e:
                        response_text = f"开始游戏失败：{str(e)}"
                        self.logger.error(f"开始游戏失败: {str(e)}", exc_info=True)
            else:
                # 判断是否为回合控制命令
                if text == "/结束回合" or text == "/end":
                    # 直接检查当前回合是否已完成，如果已完成则执行回合转换
                    current_turn = self.game_match.get_current_turn()
                    if current_turn and current_turn.is_completed():
                        result = self.game_match.handle_turn_transition()
                        response_text = result if result else "回合已结束，状态转换成功"
                    else:
                        response_text = "当前回合尚未完成，无法结束"
                else:
                    # 创建普通输入事件
                    event_type = EventType.PLAYER_ACTION if text.startswith('/') else EventType.DM_NARRATION
                    event = {
                        'type': event_type,
                        'player_id': player_id,
                        'content': text
                    }
                    response_text = "内容已记录"
                    
                    try:
                        # 处理事件
                        result = self.game_match.process_event(event)
                        if result:  # 如果事件处理返回了特定结果
                            response_text = result
                        
                        self.logger.info(f"处理事件：玩家ID：{player_id} 事件类型：{event_type} 响应：{response_text}")

                    except LLMTimeoutError:
                        response_text = "大模型请求超时，请稍后再试"
                        self.logger.warning(f"大模型请求超时：玩家ID：{player_id} 行动内容：{text}")
                    except PlayerTimeoutError:
                        response_text = "玩家输入超时，跳过本轮"
                        self.logger.warning(f"玩家输入超时：玩家ID：{player_id} 行动内容：{text}")
        except Exception as e:
            self.logger.error(f"处理玩家行动时出错: {str(e)}", exc_info=True)
            response_text = "游戏系统出现错误，请联系管理员"

        # 回复玩家
        self.reply_to_player(response_text, incoming_message)
        return AckMessage.STATUS_OK, 'OK'

if __name__ == "__main__":
    handler = GameMessageHandler(None, logging.getLogger())
    print("GameMessageHandler测试运行")

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
            # 首先判断是否以/打头，如果是，认为是指令，进一步分析指令内容
            if text.startswith('/'):
                # 处理加入游戏指令
                if text == "/加入游戏" or text == "/join":
                    try:
                        self.game_match.add_player(player_id, player_name)
                        # 注意：add_player方法内部会调用reply_to_player
                    except InvalidGameOperation as e:
                        self.reply_to_player(player_id, f"加入游戏失败：{str(e)}")
                        self.logger.warning(f"玩家加入游戏失败: {str(e)}")
                    except Exception as e:
                        self.reply_to_player(player_id, "加入游戏失败：系统错误.")
                        self.logger.error(f"玩家加入游戏失败: {str(e)}", exc_info=True)
                
                # 处理开始游戏指令
                elif text == "/开始游戏" or text == "/start":
                    if not self.game_match.current_room:
                        self.reply_to_player(player_id, "请先创建房间")
                    elif not self.game_match.current_room.players:
                        self.reply_to_player(player_id, "房间中没有玩家，请先加入游戏")
                    elif self.game_match.current_room.current_match:
                        self.reply_to_player(player_id, "当前已有进行中的游戏局，请等待当前游戏结束。")
                    else:
                        try:
                            self.game_match.start_game(scene="初始场景")
                            # 注意：start_game方法内部会调用reply_to_player
                        except Exception as e:
                            self.reply_to_player(player_id, f"开始游戏失败：{str(e)}")
                            self.logger.error(f"开始游戏失败: {str(e)}", exc_info=True)
                
                # 判断是否为回合控制命令
                elif text == "/结束回合" or text == "/end":
                    # 直接检查当前回合是否已完成，如果已完成则执行回合转换
                    current_turn = self.game_match.get_current_turn()
                    if current_turn and current_turn.is_completed():
                        result = self.game_match.handle_turn_transition()
                        if not result:
                            self.reply_to_player(player_id, "回合已结束，状态转换成功")
                        # 注意：如果result有值，handle_turn_transition内部会通过reply_to_player返回信息
                    else:
                        self.reply_to_player(player_id, "当前回合尚未完成，无法结束")

            # 不是以/开头，视为普通消息（DM叙述）
            else:
                # 创建玩家行动事件
                event = {
                    'type': EventType.PLAYER_ACTION,
                    'player_id': player_id,
                    'content': text
                }
                
                try:
                    # 处理事件
                    self.game_match.process_event(event)
                    # process_event内部会通过相应的handler处理事件，并在需要时调用reply_to_player
                    
                    self.logger.info(f"处理事件：玩家ID：{player_id} 事件类型：{EventType.PLAYER_ACTION}")

                except LLMTimeoutError:
                    self.reply_to_player(player_id, "大模型请求超时，请稍后再试")
                    self.logger.warning(f"大模型请求超时：玩家ID：{player_id} 行动内容：{text}")
                except PlayerTimeoutError:
                    self.reply_to_player(player_id, "玩家输入超时，跳过本轮")
                    self.logger.warning(f"玩家输入超时：玩家ID：{player_id} 行动内容：{text}")
        except Exception as e:
            self.logger.error(f"处理玩家行动时出错: {str(e)}", exc_info=True)
            self.reply_to_player(player_id, "游戏系统出现错误，请联系管理员")

        # 不再需要在这里强制回复，因为所有需要回复的场景都已经通过reply_to_player处理了
        return AckMessage.STATUS_OK, 'OK'

if __name__ == "__main__":
    handler = GameMessageHandler(None, logging.getLogger())
    print("GameMessageHandler测试运行")

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory
import os
import yaml
import logging
import json
import re
from typing import List, Dict, Any, Optional
from game.state.models import Match, TurnType

# 自定义异常类
class LLMTimeoutError(Exception):
    """大模型请求超时异常"""
    pass

class PlayerTimeoutError(Exception):
    """玩家输入超时异常"""
    pass

# 从配置加载API密钥和历史记录长度
with open('config/llm_settings.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# 设置OpenAI API密钥
os.environ["OPENAI_API_KEY"] = config.get('openai_api_key', '')
history_length = config.get('history_length', 50)  # 获取历史记录长度，默认为50

# 初始化记忆模块
story_memory = ConversationBufferMemory(
    memory_key="history",
    return_only_outputs=True,
    return_messages=True
)

# 初始化模型
# 使用OpenAI的模型替代Gemini
base_url = config.get('base_url', 'https://api.openai.com/v1')  # 默认值为官方OpenAI API
openai_model = config.get('model', 'gpt-3.5-turbo')
openai_pro = ChatOpenAI(base_url=base_url, model=openai_model, temperature=0.7)
openai_flash = ChatOpenAI(base_url=base_url, model=openai_model, temperature=0.5)

# JSON输出解析器
class StoryOutputParser:
    def parse(self, text: str) -> Dict[str, Any]:
        """将大语言模型输出解析为JSON格式"""
        try:
            # 尝试从文本中提取JSON部分
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 如果没有找到JSON块，尝试直接解析整个文本
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            # 如果解析失败，返回一个基本结构
            logging.warning(f"无法解析JSON输出: {text}")
            return {
                "narration": text,
                "need_dice_roll": False,
                "active_players": [],
                "attribute_changes": {}
            }

# 构建Chain
def _build_story_chain():
    # 将历史记录转换为字符串
    def format_history(vars):
        history = story_memory.load_memory_variables({})
        if isinstance(history.get('history'), list):
            return "\n".join([item.content for item in history['history']])
        return str(history.get('history', ''))

    prompt = ChatPromptTemplate.from_template(
        """
        你是一个专业的跑团游戏主持人(DM)，负责讲述故事并推进剧情。

        # 当前场景
        {current_scene}

        # 玩家信息
        {players}

        # 玩家上一回合的行动
        {player_actions}

        # 历史记录
        {history}

        请根据当前场景和玩家行动，推进故事发展。
        
        首先，判断玩家的行动是否需要进行属性检定（如力量、敏捷、智力等）。
        如果需要检定，请提供检定类型、难度值，以及检定成功和失败两种情况下的故事发展和属性变化。
        如果不需要检定，直接描述故事的发展。

        请以JSON格式输出，包含以下字段：
        1. need_dice_roll: 布尔值，表示是否需要扔色子进行判定
        2. roll_type: 如果需要判定，说明判定类型（如"力量"、"敏捷"等）
        3. difficulty: 如果需要判定，说明难度（1-20的数字）
        4. success_narration: 如果需要判定，描述判定成功时的故事发展
        5. failure_narration: 如果需要判定，描述判定失败时的故事发展
        6. success_attribute_changes: 如果需要判定，描述判定成功时的属性变化
        7. failure_attribute_changes: 如果需要判定，描述判定失败时的属性变化
        8. narration: 如果不需要判定，直接描述故事发展
        9. active_players: 数组，包含下一回合需要行动的玩家ID
        10. attribute_changes: 如果不需要判定，描述属性变化

        示例输出（需要判定的情况）：
        ```json
        {
            "need_dice_roll": true,
            "roll_type": "力量",
            "difficulty": 15,
            "success_narration": "Alice成功推开了沉重的石门，露出了一条通往地下的楼梯。",
            "failure_narration": "Alice尝试推开石门，但门纹丝不动，似乎需要更大的力量。",
            "success_attribute_changes": {"player1": {"stamina": -5}},
            "failure_attribute_changes": {"player1": {"stamina": -10, "health": -5}},
            "active_players": ["player1", "player2"]
        }
        ```

        示例输出（不需要判定的情况）：
        ```json
        {
            "need_dice_roll": false,
            "narration": "你们轻松地穿过森林，来到了一片开阔地。远处可以看到一座古老的城堡。",
            "active_players": ["player1", "player2", "player3"],
        }
        ```
        """
    )

    chain = (
        {
            "current_scene": RunnablePassthrough(),
            "players": RunnablePassthrough(),
            "history": format_history
        }
        | prompt
        | openai_pro
        | StrOutputParser()
    )

    return chain

story_chain = _build_story_chain()

class DMProcessingChain:
    def __init__(self):
        self.story_parser = StoryOutputParser()
    
    def process_dm_turn(self, match: Match, players: List[str]) -> Dict[str, Any]:
        """处理DM回合，生成故事叙述和下一回合激活玩家"""
        import random
        from typing import List, Dict, Any, Optional
        
        current_match = match
        current_scene = current_match.scene
        story_history = getattr(match, 'story_history', [])
        
        # 获取上一个玩家回合的行动（如果有）
        player_actions_text = "没有玩家行动"
        if len(current_match.turns) > 1:
            # 获取上一个回合（假设是玩家回合）
            prev_turn = current_match.turns[-2]  # current_turn是当前DM回合，-2是上一个玩家回合
            if prev_turn.turn_type == TurnType.PLAYER and prev_turn.actions:
                # 收集玩家行动
                actions = []
                for player_id, action in prev_turn.actions.items():
                    # 尝试获取玩家名称
                    player_name = player_id
                    for p in current_match.players if hasattr(current_match, 'players') else []:
                        if p.id == player_id:
                            player_name = p.name
                            break
                    
                    actions.append(f"{player_name}({player_id}): {action}")
                
                player_actions_text = "\n".join(actions)

        context = {
            "current_scene": current_scene,
            "players": ", ".join(players),
            "player_actions": player_actions_text,
            "history": "\n".join(story_history[-history_length:])
        }

        try:
            # 调用大语言模型
            narration = story_chain.invoke(context)
            
            # 解析输出为JSON格式
            result = self.story_parser.parse(narration)
            
            # 处理判定逻辑
            if result.get("need_dice_roll", False):
                # 需要判定，模拟骰子结果
                dice_type = 20  # 默认使用20面骰子
                roll_result = random.randint(1, dice_type)
                
                # 判断成功或失败
                difficulty = result.get("difficulty", 10)
                success = roll_result >= difficulty
                
                # 根据成功或失败选择对应的叙述
                final_narration = result.get("success_narration" if success else "failure_narration", 
                                          "骰子结果：" + str(roll_result))
                
                # 根据成功或失败选择对应的属性变化
                attribute_changes = result.get("success_attribute_changes" if success else "failure_attribute_changes", {})
                
                # 记录判定结果
                logging.info(f"判定类型：{result.get('roll_type', '未知')}，难度：{difficulty}，骰子结果：{roll_result}，{'成功' if success else '失败'}")
                
                # 更新记忆
                story_memory.save_context(
                    {"input": context["current_scene"] + "\n" + context["player_actions"]},
                    {"output": final_narration}
                )
                
                # 返回结果
                return {
                    "narration": final_narration,
                    "active_players": result.get("active_players", players[:2]),
                    "need_dice_roll": False,  # 已经完成判定
                    "roll_type": result.get("roll_type", ""),
                    "difficulty": difficulty,
                    "roll_result": roll_result,
                    "success": success,
                    "attribute_changes": attribute_changes
                }
            else:
                # 不需要判定，直接使用narration
                final_narration = result.get("narration", "")
                
                # 更新记忆
                story_memory.save_context(
                    {"input": context["current_scene"] + "\n" + context["player_actions"]},
                    {"output": final_narration}
                )
                
                # 返回结果
                return {
                    "narration": final_narration,
                    "active_players": result.get("active_players", players[:2]),
                    "need_dice_roll": False,
                    "attribute_changes": result.get("attribute_changes", {})
                }
        except Exception as e:
            logging.error(f"故事生成失败：{str(e)}")
            raise

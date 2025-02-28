from langchain_openai.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory
import os
import yaml
import logging  # 添加此行以导入logging模块

# 自定义异常类
class LLMTimeoutError(Exception):
    """大模型请求超时异常"""
    pass

class PlayerTimeoutError(Exception):
    """玩家输入超时异常"""
    pass

# 从配置加载API密钥和历史记录长度
with open('config/llm_settings.yaml', 'r') as f:
    config = yaml.safe_load(f)

os.environ["OPENAI_API_KEY"] = config['openai_api_key']
history_length = config.get('history_length', 50)  # 获取历史记录长度，默认为50

# 初始化记忆模块
story_memory = ConversationBufferMemory(memory_key="history", return_only_outputs=True)

# 初始化模型
gpt4o = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
gpt3 = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.5)

# 构建Chain
def _build_story_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个专业的跑团游戏主持人，当前故事历史：{history}"),
        ("human", "当前剧情：{current_scene}\n请推进剧情并选择需要行动的玩家：{players}")
    ])
    
    return (
        {"current_scene": RunnablePassthrough(), 
         "players": RunnablePassthrough(),
         "history": story_memory.load_memory_variables()}
        | prompt
        | gpt4o
        | StrOutputParser()
    )

def _build_action_chain():
    prompt = ChatPromptTemplate.from_template(
        "处理玩家动作：{action}\n根据当前场景：{scene}"
    )
    return (
        {"action": RunnablePassthrough(), "scene": RunnablePassthrough()}
        | prompt
        | gpt3
        | StrOutputParser()
    )

story_chain = _build_story_chain()
action_chain = _build_action_chain()

class TurnProcessingChain:
    def process_dm_turn(self, state, players):
        current_round = state.current_room.current_round
        
        context = {
            "current_scene": current_round.scene,
            "players": ", ".join(players),
            "history": "\n".join(current_round.story_history[-history_length:])  # 使用配置的历史记录长度
        }
        
        try:
            narration = story_chain.invoke(context)
            
            # 更新记忆和回合历史
            story_memory.save_context(
                {"input": context["current_scene"]},
                {"output": narration}
            )
            current_round.story_history.append(narration)
            
            return {
                "narration": narration,
                "active_players": players[:2]
            }
        except Exception as e:
            logging.error(f"故事生成失败：{str(e)}")
            raise

    def process_player_actions(self, state):
        actions = "\n".join([f"{a['player_id']}: {a['action']}" for a in state.player_actions])
        try:
            result = action_chain.invoke({"action": actions, "scene": state.current_scene})
            return {
                "scene_update": result,
                "result": f"剧情更新：{result}"
            }
        except TimeoutError:
            raise PlayerTimeoutError("玩家输入超时")

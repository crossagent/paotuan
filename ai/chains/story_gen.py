from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import PydanticOutputParser
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from models.entities import Match, TurnType
import os
import yaml
import logging
import random

# Pydantic 模型定义
class PlayerInfo(BaseModel):
    """玩家角色信息模型"""
    id: str = Field(..., description="角色ID")
    name: str = Field(..., description="角色姓名")
    gender: str = Field(..., description="角色性别")
    age: int = Field(..., description="角色年龄", ge=12, le=100)
    profession: str = Field(..., description="角色职业")
    health: int = Field(default=100, description="生命值", ge=0, le=100)
    items: List[str] = Field(default_factory=list, description="拥有的物品列表")

class AttributeChange(BaseModel):
    """属性变更模型"""
    health: Optional[int] = Field(None, description="生命值变化")

class DiceRollResult(BaseModel):
    """骰子检定结果模型"""
    action_desc: str = Field(..., description="行动描述")
    difficulty: int = Field(..., description="检定难度(1-20)", ge=1, le=20)
    success_narration: str = Field(..., description="检定成功时的描述")
    failure_narration: str = Field(..., description="检定失败时的描述")
    success_attribute_changes: Dict[str, AttributeChange] = Field(
        default_factory=dict,
        description="检定成功时的生命值变化"
    )
    failure_attribute_changes: Dict[str, AttributeChange] = Field(
        default_factory=dict,
        description="检定失败时的生命值变化"
    )

class StoryResponse(BaseModel):
    """故事响应模型"""
    need_dice_roll: bool = Field(..., description="是否需要骰子检定")
    narration: Optional[str] = Field(None, description="故事描述(不需要检定时)")
    dice_roll: Optional[DiceRollResult] = Field(None, description="骰子检定相关信息")
    active_players: List[str] = Field(..., description="下一回合激活的玩家ID列表")

class StoryChain:
    def __init__(self):
        # 从配置加载设置
        with open('config/llm_settings.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        # 初始化设置
        self.history_length = config.get('history_length', 50)
        base_url = config.get('base_url', 'https://api.openai.com/v1')
        openai_model = config.get('model', 'gpt-3.5-turbo')
        os.environ["OPENAI_API_KEY"] = config.get('openai_api_key', '')

        # 初始化组件
        self.llm = ChatOpenAI(
            base_url=base_url,
            model=openai_model,
            temperature=0.7
        )
        self.memory = ConversationBufferMemory(
            memory_key="history",
            return_messages=True
        )
        self.output_parser = PydanticOutputParser(pydantic_object=StoryResponse)

        # 构建提示模板
        self.prompt = ChatPromptTemplate.from_template(
            template="""你是一个专业的跑团游戏主持人(DM)。
            
            当前场景：{current_scene}
            玩家信息：{players}
            玩家行动：{player_actions}
            历史记录：{history}

            根据以上信息推进故事发展。判断是否需要属性检定，会修改到属性或消耗物品的行为一定要进行判定。

            {format_instructions}
            """
        )

        # 构建Chain
        self.chain = (
            {
                "current_scene": RunnablePassthrough(),
                "players": RunnablePassthrough(),
                "player_actions": RunnablePassthrough(),
                "history": self._format_history,
                "format_instructions": lambda _: self.output_parser.get_format_instructions()
            }
            | self.prompt
            | self.llm
            | self.output_parser
        )

    def _format_turn_result(self, result: Dict[str, Any], player_name: str) -> str:
        """格式化单个行动结果"""
        if result.get('need_dice_roll'):
            roll_info = (
                f"系统: {player_name}进行了{result['roll_type']}检定，"
                f"难度为{result['difficulty']}，"
                f"骰子结果为{result['roll_result']}，"
                f"{'成功' if result['success'] else '失败'}。\n"
            )
            
            # 添加结果描述
            roll_info += f"DM: {result['narration']}\n"
            
            # 添加属性变化
            if result.get('attribute_changes'):
                changes = []
                for char_id, change in result['attribute_changes'].items():
                    if change.health:
                        changes.append(f"{char_id}的生命值变化{change.health}")
                if changes:
                    roll_info += f"系统: {', '.join(changes)}\n"
                    
            return roll_info
        else:
            return f"DM: {result['narration']}\n"

    def _format_history(self, vars: Dict[str, Any]) -> str:
        """格式化历史记录"""
        history = self.memory.load_memory_variables({})
        messages = history.get('history', [])
        
        if not isinstance(messages, list):
            return str(messages)
            
        formatted_history = []
        for msg in messages[-self.history_length:]:
            # 根据消息类型格式化
            if "玩家" in msg.content:
                formatted_history.append(msg.content)
            elif "系统" in msg.content:
                formatted_history.append(msg.content)
            else:
                formatted_history.append(f"DM: {msg.content}")
                
        return "\n".join(formatted_history)

    def get_formatted_history(self) -> str:
        """获取格式化的历史记录
        
        Returns:
            str: 格式化的历史记录字符串，包含玩家行动、系统提示和DM描述
        """
        history = self.memory.load_memory_variables({})
        messages = history.get('history', [])
        
        if not isinstance(messages, list):
            return str(messages)
            
        formatted_history = []
        for msg in messages[-self.history_length:]:
            # 根据消息类型格式化
            content = msg.content
            if isinstance(content, str):
                formatted_history.append(content)
                
        return "\n".join(formatted_history)

    def _save_formatted_history(self, context: Dict[str, Any], result: Dict[str, Any]) -> None:
        """保存格式化的历史记录"""
        # 保存玩家行动
        if context['player_actions'] != "没有玩家行动":
            self.memory.save_context(
                {"input": ""},
                {"output": context['player_actions']}
            )
        
        # 保存检定结果和DM描述
        self.memory.save_context(
            {"input": ""},
            {"output": self._format_turn_result(result, context.get('player_name', '未知玩家'))}
        )

    def _handle_dice_roll(self, dice_result: DiceRollResult) -> Dict[str, Any]:
        """处理骰子检定"""
        roll = random.randint(1, 20)
        success = roll >= dice_result.difficulty
        
        return {
            "narration": dice_result.success_narration if success else dice_result.failure_narration,
            "attribute_changes": (
                dice_result.success_attribute_changes if success 
                else dice_result.failure_attribute_changes
            ),
            "roll_result": roll,
            "success": success,
            "roll_type": dice_result.action_desc,
            "difficulty": dice_result.difficulty
        }

    def process_turn(self, match: Match, players: List[str]) -> Dict[str, Any]:
        """处理一个回合"""
        try:
            # 准备上下文
            context = self._prepare_context(match, players)
            
            # 生成响应 - 使用同步调用
            response = self.chain.invoke(context)
            
            # 处理响应
            if response.need_dice_roll and response.dice_roll:
                result = self._handle_dice_roll(response.dice_roll)
            else:
                result = {
                    "narration": response.narration,
                    "need_dice_roll": False
                }
            
            # 保存格式化的历史记录
            self._save_formatted_history(context, result)
            
            return {
                **result,
                "active_players": response.active_players
            }
            
        except Exception as e:
            logging.error(f"处理回合失败: {str(e)}")
            raise

    def _prepare_context(self, match: Match, players: List[str]) -> Dict[str, Any]:
        """准备上下文信息"""
        # 获取上一个回合的玩家行动
        player_actions = self._get_previous_actions(match)
        
        return {
            "current_scene": match.scene,
            "players": ", ".join(players),
            "player_actions": player_actions
        }

    def _get_previous_actions(self, match: Match) -> str:
        """获取上一回合的玩家行动"""
        if len(match.turns) < 2:
            return "没有玩家行动"
            
        prev_turn = match.turns[-2]
        if (prev_turn.turn_type != TurnType.PLAYER or not prev_turn.actions):
            return "没有玩家行动"
            
        actions = []
        for player_id, action in prev_turn.actions.items():
            player_name = self._get_player_name(match, player_id)
            actions.append(f"{player_name}({player_id}): {action}")
            
        return "\n".join(actions)

    def _get_player_name(self, match: Match, player_id: str) -> str:
        """获取玩家名称"""
        if not hasattr(match, 'players'):
            return player_id
            
        for player in match.players:
            if player.id == player_id:
                return player.name
                
        return player_id

# 在文件末尾添加以下代码
def main():
    """测试主函数"""
    # 模拟游戏数据
    class Player:
        def __init__(self, id: str, name: str):
            self.id = id
            self.name = name

    class Turn:
        def __init__(self, turn_type: TurnType, actions: Dict[str, str] = None):
            self.turn_type = turn_type
            self.actions = actions or {}

    class TestMatch:
        def __init__(self):
            self.scene = "一个昏暗的地下城入口前，石壁上的火把摇曳着微弱的光芒。"
            self.players = [
                PlayerInfo(
                    id="p1",
                    name="战士小王",
                    gender="男",
                    age=25,
                    profession="战士",
                    health=100,
                    items=["大剑", "盾牌", "治疗药水"]
                ),
                PlayerInfo(
                    id="p2",
                    name="法师小李",
                    gender="女",
                    age=22,
                    profession="法师",
                    health=100,
                    items=["法杖", "魔法书", "魔力药水"]
                ),
                PlayerInfo(
                    id="p3",
                    name="盗贼小张",
                    gender="男",
                    age=20,
                    profession="盗贼",
                    health=100,
                    items=["匕首", "撬锁工具", "隐身斗篷"]
                )
            ]
            self.turns = [
                Turn(TurnType.PLAYER, {
                    "p1": "我想查看周围是否有危险",
                    "p2": "我准备施放照明术",
                    "p3": "我躲在暗处观察"
                })
            ]

    try:
        story_chain = StoryChain()
        match = TestMatch()
        players = ["p1", "p2", "p3"]
        
        # 处理回合
        result = story_chain.process_turn(match, players)
        
        # 打印结果
        print("\n=== 处理结果 ===")
        print(f"故事描述: {result.get('narration', '无描述')}")
        
        if result.get('need_dice_roll'):
            print("\n骰子检定结果:")
            print(f"检定类型: {result.get('roll_type')}")
            print(f"难度: {result.get('difficulty')}")
            print(f"结果: {result.get('roll_result')}")
            print(f"是否成功: {'成功' if result.get('success') else '失败'}")
        
        print("\n属性变化:")
        for char_id, changes in result.get('attribute_changes', {}).items():
            print(f"{char_id}: {changes}")
        
        print("\n下回合激活玩家:", result.get('active_players', []))
        
        # 打印历史记录
        print("\n=== 历史记录 ===")
        history = story_chain.get_formatted_history()
        print(history)
        
    except Exception as e:
        logging.error(f"测试失败: {str(e)}")
        raise

if __name__ == "__main__":
    main()  # 直接调用，不需要 asyncio

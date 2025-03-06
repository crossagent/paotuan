from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Literal
import logging
import yaml
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class LocationUpdate(BaseModel):
    """位置更新模型"""
    player_id: str = Field(..., description="玩家ID")
    new_location: str = Field(..., description="新位置，格式为'楼层/房间'")

class ItemUpdate(BaseModel):
    """物品更新模型"""
    player_id: str = Field(..., description="玩家ID")
    item: str = Field(..., description="物品名称")
    action: Literal["add", "remove"] = Field(..., description="添加或移除物品")

class StoryResponse(BaseModel):
    """故事响应模型"""
    narration: str = Field(..., description="故事描述")
    need_dice_roll: bool = Field(..., description="是否需要骰子检定")
    difficulty: Optional[int] = Field(None, description="检定难度(1-20)")
    action_desc: Optional[str] = Field(None, description="行动描述")
    active_players: List[str] = Field(..., description="下一回合激活的玩家ID列表")
    # 新增字段
    location_updates: List[LocationUpdate] = Field(default_factory=list, description="玩家位置更新")
    item_updates: List[ItemUpdate] = Field(default_factory=list, description="玩家物品更新")
    plot_progress: Optional[int] = Field(None, description="剧情节点进度，如果需要推进")
    game_over: bool = Field(default=False, description="游戏是否结束")
    game_result: Optional[Literal["victory", "failure"]] = Field(None, description="游戏结果")

class AIService(ABC):
    """AI服务接口"""
    
    @abstractmethod
    async def generate_narration(self, context: Dict[str, Any]) -> StoryResponse:
        """生成叙事内容"""
        pass

class OpenAIService(AIService):
    """使用OpenAI实现的AI服务"""
    
    def __init__(self, config_path: str = "config/llm_settings.yaml"):
        # 尝试从环境变量加载API密钥
        api_key = os.environ.get('OPENAI_API_KEY', '')
        model = os.environ.get('OPENAI_MODEL', '')
        temperature = os.environ.get('OPENAI_TEMP', '')
        
        # 尝试加载配置文件
        config = {}
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            logging.warning(f"配置文件 {config_path} 未找到，将使用环境变量或默认值")
            
        # 环境变量优先级高于配置文件
        self.llm = ChatOpenAI(
            api_key=api_key or config.get('openai_api_key', ''),
            model=model or config.get('model', 'gpt-3.5-turbo'),
            temperature=float(temperature) if temperature else config.get('temperature', 0.7)
        )
        
        # 初始化输出解析器
        self.output_parser = PydanticOutputParser(pydantic_object=StoryResponse)
        
        # 构建提示模板
        self.prompt = ChatPromptTemplate.from_template(
            template="""你是一个专业的跑团游戏主持人(DM)。
            
            {scenario_info}
            
            当前场景：{current_scene}
            玩家信息：{players}
            玩家行动：{player_actions}
            历史记录：{history}
            {dice_results}

            根据以上信息和剧本引导推进故事发展。请特别注意：
            1. 始终按照剧本设定的方向发展故事
            2. 清楚地描述玩家当前所处的位置及其细节
            3. 提及当前位置可见的重要道具和NPC
            4. 根据玩家收集的道具和当前位置判断剧情进度
            5. 根据剧情节点提供适当的线索和挑战

            【重要】你需要自动更新玩家的位置和物品：
            1. 当玩家移动到新位置时，返回location_updates字段指定新位置
            2. 当玩家获得或失去物品时，返回item_updates字段更新物品列表
            3. 当剧情需要推进到下一个事件时，返回plot_progress字段

            【重要】关于胜利和失败条件：
            1. 持续评估玩家是否已达成胜利条件或失败条件
            2. 如果玩家满足任一胜利条件，在narration中说明玩家获胜原因，并将游戏标记为结束
            3. 如果玩家满足任一失败条件，在narration中说明玩家失败原因，并将游戏标记为结束
            4. 当游戏结束时，需要在narration中明确标识"游戏结束"

            【重要】关于判定：
            1. 判定是一个重要且严肃的事件，不应频繁使用。
            2. 只有在关键时刻、重大挑战或有显著风险的行动才需要判定。
            3. 判定失败会导致玩家受到伤害，生命值会减少。
            4. 会修改到属性或消耗物品的行为一定要进行判定。
            5. 普通的移动、交谈、观察等低风险行为通常不需要判定。

            注意：active_players字段必须使用玩家ID而不是玩家名称。有效的玩家ID列表：{player_ids}

            {format_instructions}
            """
        )
    
    async def generate_narration(self, context: Dict[str, Any], scenario: Optional[Any] = None) -> StoryResponse:
        """生成叙事内容"""
        try:
            # 准备输入
            input_data = {
                "current_scene": context.get("current_scene", ""),
                "players": context.get("players", ""),
                "player_actions": context.get("player_actions", ""),
                "history": context.get("history", ""),
                "player_ids": context.get("player_ids", []),
                "format_instructions": self.output_parser.get_format_instructions()
            }
            
            # 处理掷骰子结果
            dice_results = context.get("dice_results", None)
            if dice_results and dice_results.get("summary"):
                dice_results_text = "判定结果:\n"
                for result in dice_results["summary"]:
                    player_action = result.get('action', '行动')
                    dice_results_text += f"玩家 {result['player_id']} 尝试 {player_action}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
                input_data["dice_results"] = dice_results_text
            else:
                input_data["dice_results"] = ""
                
            # 添加剧本信息（如果有）
            if scenario:
                try:
                    # 确定当前事件
                    current_event_index = scenario.current_event_index 
                    current_event = scenario.events[current_event_index].content if current_event_index < len(scenario.events) else None
                    next_event = scenario.events[current_event_index + 1].content if current_event_index + 1 < len(scenario.events) else None
                    
                    # 获取当前位置描述
                    location_desc, visible_items = self._get_location_description(scenario)
                    
                    # 整合剧本信息
                    scenario_context = (
                        f"剧本名称: {scenario.name}\n"
                        f"世界背景: {scenario.world_background}\n"
                        f"主要场景: {scenario.main_scene}\n"
                    )
                    
                    # 添加胜利和失败条件
                    if scenario.victory_conditions:
                        scenario_context += f"胜利条件: {'; '.join(scenario.victory_conditions)}\n"
                    
                    if scenario.failure_conditions:
                        scenario_context += f"失败条件: {'; '.join(scenario.failure_conditions)}\n"
                    
                    # 添加位置信息
                    scenario_context += f"玩家当前位置: {scenario.player_location}\n"
                    scenario_context += f"当前位置描述: {location_desc}\n"
                    
                    # 添加进度信息
                    scenario_context += f"事件进度: {current_event_index + 1}/{len(scenario.events)}\n"
                    if current_event:
                        scenario_context += f"当前事件: {current_event}\n"
                    if next_event:
                        scenario_context += f"下一个事件发展方向: {next_event}\n"
                    
                    # 添加可见道具
                    if visible_items:
                        items_desc = []
                        for item in visible_items:
                            items_desc.append(f"{item['item']}（位于{item['position']}）")
                        scenario_context += f"当前位置可见道具: {', '.join(items_desc)}\n"
                    
                    # 添加已收集道具
                    if scenario.collected_items:
                        scenario_context += f"已收集道具: {', '.join(scenario.collected_items)}\n"
                    
                    # 添加角色信息
                    location_characters = []
                    for character in scenario.characters:
                        if character.location == scenario.player_location and character.encountered:
                            location_characters.append(f"{character.name} - {character.description}")
                    
                    if location_characters:
                        scenario_context += f"当前位置的角色: {'; '.join(location_characters)}\n"
                    
                    # 添加到输入数据
                    input_data["scenario_info"] = scenario_context
                except Exception as e:
                    logger.exception(f"处理剧本信息失败: {str(e)}")
                    input_data["scenario_info"] = ""
            else:
                input_data["scenario_info"] = ""
            
            # 生成提示
            prompt = self.prompt.format(**input_data)
            
            # 调用模型
            model_result = self.llm.invoke(prompt)
            
            # 解析输出
            result = self.output_parser.parse(model_result.content)
            
            return result
        except Exception as e:
            logger.exception(f"生成叙事失败: {str(e)}")
            # 返回一个默认响应
            return StoryResponse(
                narration="系统遇到错误，无法生成叙事",
                need_dice_roll=False,
                active_players=[]
            )
            
    def _get_location_description(self, scenario) -> tuple[str, list]:
        """获取当前位置的描述和可见道具"""
        if not scenario.player_location:
            return "", []
            
        # 查找当前场景
        current_scene = None
        for scene in scenario.scenes:
            if scene.name == scenario.player_location:
                current_scene = scene
                break
                
        if not current_scene:
            return "", []
            
        # 返回场景描述和可能的道具
        possible_items = []
        if current_scene.puzzle:
            for item in current_scene.puzzle.possible_items:
                if item not in scenario.collected_items:
                    possible_items.append({
                        "position": current_scene.name,
                        "item": item
                    })
                    
        return current_scene.description, possible_items

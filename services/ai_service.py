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
            3. 当剧情需要推进到下一个节点时，返回plot_progress字段

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
                # 确定当前剧情节点
                current_plot_index = scenario.current_plot_point 
                current_plot = scenario.plot_points[current_plot_index] if current_plot_index < len(scenario.plot_points) else None
                next_plot = scenario.plot_points[current_plot_index + 1] if current_plot_index + 1 < len(scenario.plot_points) else None
                
                # 获取当前位置描述
                location_desc, visible_items = self._get_location_description(scenario)
                
                # 整合剧本信息
                scenario_context = (
                    f"剧本名称: {scenario.name}\n"
                    f"故事背景: {scenario.background}\n"
                    f"游戏目标: {scenario.goal}\n"
                )
                
                # 添加位置信息
                scenario_context += f"玩家当前位置: {scenario.player_location}\n"
                scenario_context += f"当前位置描述: {location_desc}\n"
                
                # 添加进度信息
                scenario_context += f"剧情进度: {current_plot_index + 1}/{len(scenario.plot_points)}\n"
                if current_plot:
                    scenario_context += f"当前剧情节点: {current_plot}\n"
                if next_plot:
                    scenario_context += f"下一个剧情发展方向: {next_plot}\n"
                
                # 添加可见道具
                if visible_items:
                    items_desc = []
                    for item in visible_items:
                        items_desc.append(f"{item['item']}（位于{item['position']}）")
                    scenario_context += f"当前位置可见道具: {', '.join(items_desc)}\n"
                
                # 添加已收集道具
                if scenario.collected_items:
                    scenario_context += f"已收集道具: {', '.join(scenario.collected_items)}\n"
                
                # 添加NPC信息
                if scenario.npcs:
                    # 筛选当前位置的NPC
                    location_npcs = []
                    for npc in scenario.npcs:
                        if npc.location == scenario.player_location:
                            location_npcs.append(f"{npc.name} - {npc.description}")
                    
                    if location_npcs:
                        scenario_context += f"当前位置的NPC: {'; '.join(location_npcs)}\n"
                
                # 添加到输入数据
                input_data["scenario_info"] = scenario_context
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
        """获取当前位置的描述和可见道具
        
        Args:
            scenario: 剧本对象
            
        Returns:
            当前位置的描述和可见道具列表
        """
        if not scenario.player_location:
            return "", []
            
        # 获取当前位置
        floor_name, room_name = scenario.player_location.split("/")
        
        # 查找楼层和房间
        for floor in scenario.map.floors:
            if floor.name == floor_name:
                for room in floor.rooms:
                    if room.name == room_name:
                        # 整合房间描述
                        description = f"{floor.description} - {room.description}"
                        
                        # 获取未收集的道具
                        visible_items = []
                        for key_item in room.key_items:
                            if not key_item.collected:
                                visible_items.append({
                                    "position": key_item.position,
                                    "item": key_item.item
                                })
                        
                        return description, visible_items
                        
        return "", []

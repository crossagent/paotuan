from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import logging
import yaml
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class StoryResponse(BaseModel):
    """故事响应模型"""
    narration: str = Field(..., description="故事描述")
    need_dice_roll: bool = Field(..., description="是否需要骰子检定")
    difficulty: Optional[int] = Field(None, description="检定难度(1-20)")
    action_desc: Optional[str] = Field(None, description="行动描述")
    active_players: List[str] = Field(..., description="下一回合激活的玩家ID列表")

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
            
            当前场景：{current_scene}
            玩家信息：{players}
            玩家行动：{player_actions}
            历史记录：{history}
            {dice_results}

            根据以上信息推进故事发展。判断是否需要属性检定，会修改到属性或消耗物品的行为一定要进行判定。

            {format_instructions}
            """
        )
    
    async def generate_narration(self, context: Dict[str, Any]) -> StoryResponse:
        """生成叙事内容"""
        try:
            # 准备输入
            input_data = {
                "current_scene": context.get("current_scene", ""),
                "players": context.get("players", ""),
                "player_actions": context.get("player_actions", ""),
                "history": context.get("history", ""),
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

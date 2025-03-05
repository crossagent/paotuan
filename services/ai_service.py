from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging
import yaml

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
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        # 初始化LLM
        self.llm = ChatOpenAI(
            api_key=config.get('openai_api_key', ''),
            model=config.get('model', 'gpt-3.5-turbo'),
            temperature=config.get('temperature', 0.7)
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

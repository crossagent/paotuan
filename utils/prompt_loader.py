from langsmith import Client
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
import os
from typing import Dict, Any, Optional, Union, List

class PromptLoader:
    """
    从LangSmith加载prompt模板的工具类
    """
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化PromptLoader

        Args:
            api_key: LangSmith API密钥，如果不提供则尝试从环境变量获取
        """
        self.api_key = api_key or os.environ.get("LANGSMITH_API_KEY")
        if not self.api_key:
            raise ValueError("需要提供LANGSMITH_API_KEY或设置环境变量")
        self.client = Client(api_key=self.api_key)
        
    def pull_prompt(self, name: str, include_model: bool = False) -> Union[Dict[str, Any], ChatPromptTemplate, PromptTemplate]:
        """
        从LangSmith拉取prompt

        Args:
            name: prompt的名称
            include_model: 是否返回LangChain的模板对象

        Returns:
            如果include_model为True，返回ChatPromptTemplate或PromptTemplate对象
            否则返回包含prompt信息的字典
        """
        prompt = self.client.pull_prompt(name, include_model=include_model)
        return prompt
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        列出LangSmith中的所有prompts

        Returns:
            包含prompt信息的字典列表
        """
        prompts = self.client.list_prompts()
        return list(prompts)
    
    def get_prompt_versions(self, prompt_id: str) -> List[Dict[str, Any]]:
        """
        获取指定prompt的所有版本

        Args:
            prompt_id: prompt的ID

        Returns:
            包含prompt版本信息的字典列表
        """
        versions = self.client.list_prompt_versions(prompt_id=prompt_id)
        return list(versions)

# 使用示例
def get_prompt_example() -> None:
    """
    使用示例：从LangSmith获取prompt
    """
    # 创建一个LANGSMITH_API_KEY在Settings > API Keys
    loader = PromptLoader()
    
    # 拉取prompt，不包含模型
    prompt_info = loader.pull_prompt("code_assist_manager")
    print(f"Prompt信息: {prompt_info}")
    
    # 拉取prompt，包含模型
    prompt_template = loader.pull_prompt("code_assist_manager", include_model=True)
    print(f"Prompt模板类型: {type(prompt_template)}")
    
    # 如果是ChatPromptTemplate，可以直接使用
    if isinstance(prompt_template, (ChatPromptTemplate, PromptTemplate)):
        # 使用模板生成提示
        formatted_prompt = prompt_template.format(
            # 根据模板需要的变量提供值
            code="def hello(): print('Hello, world!')",
            question="如何优化这个函数?"
        )
        print(f"格式化后的提示: {formatted_prompt}")

if __name__ == "__main__":
    get_prompt_example()

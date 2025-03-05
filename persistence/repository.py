from abc import ABC, abstractmethod
import os
import json
import logging
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

class Repository(ABC):
    """数据仓库抽象基类"""
    
    @abstractmethod
    async def save(self, key: str, data: Any) -> None:
        """保存数据"""
        pass
    
    @abstractmethod
    async def load(self, key: str) -> Optional[Any]:
        """加载数据"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """删除数据"""
        pass
    
    @abstractmethod
    async def list_keys(self) -> List[str]:
        """列出所有键"""
        pass

class FileRepository(Repository):
    """文件数据仓库"""
    
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
    
    def _get_path(self, key: str) -> str:
        """获取文件路径"""
        return os.path.join(self.base_dir, f"{key}.json")
    
    async def save(self, key: str, data: Any) -> None:
        """保存数据到文件"""
        path = self._get_path(key)
        
        try:
            # 如果数据是Pydantic模型
            if isinstance(data, BaseModel):
                data = data.dict()
                
            # 写入文件
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"数据已保存: {key}")
        except Exception as e:
            logger.error(f"保存数据失败: {key}, {str(e)}")
            raise
    
    async def load(self, key: str) -> Optional[Any]:
        """从文件加载数据"""
        path = self._get_path(key)
        
        if not os.path.exists(path):
            logger.debug(f"数据不存在: {key}")
            return None
            
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logger.debug(f"数据已加载: {key}")
            return data
        except Exception as e:
            logger.error(f"加载数据失败: {key}, {str(e)}")
            return None
    
    async def delete(self, key: str) -> None:
        """删除数据文件"""
        path = self._get_path(key)
        
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"数据已删除: {key}")
            except Exception as e:
                logger.error(f"删除数据失败: {key}, {str(e)}")
                raise
    
    async def list_keys(self) -> List[str]:
        """列出所有键"""
        keys = []
        
        for filename in os.listdir(self.base_dir):
            if filename.endswith('.json'):
                keys.append(filename[:-5])  # 去掉.json后缀
                
        return keys

from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
import logging
from datetime import datetime

from models.entities import Character

logger = logging.getLogger(__name__)

class CharacterContext:
    """角色上下文，提供Character实体的上下文环境"""
    
    def __init__(self, character: Character):
        """初始化角色上下文
        
        Args:
            character: Character - 角色实体
        """
        self.character = character
        
    def dump_state(self) -> Dict[str, Any]:
        """返回当前状态供Inspector使用
        
        Returns:
            Dict[str, Any]: 角色状态
        """
        return {
            "id": self.character.id,
            "name": self.character.name,
            "player_id": self.character.player_id,
            "health": self.character.health,
            "max_health": self.character.max_health,
            "attributes": self.character.attributes
        }
    
    @classmethod
    def create_character(cls, name: str, player_id: Optional[str] = None, 
                        attributes: Dict[str, Any] = None) -> "CharacterContext":
        """创建新的角色
        
        Args:
            name: str - 角色名称
            player_id: Optional[str] - 玩家ID，如果为None则表示NPC
            attributes: Dict[str, Any] - 角色属性
            
        Returns:
            CharacterContext - 新创建的角色上下文
        """
        character_id = str(uuid.uuid4())
        new_character = Character(
            id=character_id,
            name=name,
            player_id=player_id,
            attributes=attributes or {}
        )
        
        logger.info(f"创建新角色: ID={character_id}, 名称={name}, 玩家ID={player_id or 'NPC'}")
        
        return cls(new_character)
    
    def set_player(self, player_id: Optional[str]) -> None:
        """设置角色的玩家ID
        
        Args:
            player_id: Optional[str] - 玩家ID，如果为None则表示NPC
        """
        old_player_id = self.character.player_id
        self.character.player_id = player_id
        
        logger.info(f"角色 {self.character.name} (ID: {self.character.id}) 的玩家从 {old_player_id or 'NPC'} 变更为 {player_id or 'NPC'}")
    
    def set_attribute(self, key: str, value: Any) -> None:
        """设置角色属性
        
        Args:
            key: str - 属性名
            value: Any - 属性值
        """
        old_value = self.character.attributes.get(key)
        self.character.attributes[key] = value
        
        logger.info(f"角色 {self.character.name} (ID: {self.character.id}) 的属性 {key} 从 {old_value} 变更为 {value}")
    
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取角色属性
        
        Args:
            key: str - 属性名
            default: Any - 默认值，如果属性不存在则返回此值
            
        Returns:
            Any - 属性值
        """
        return self.character.attributes.get(key, default)
    
    def modify_health(self, amount: int) -> int:
        """修改角色生命值
        
        Args:
            amount: int - 生命值变化量，正数为增加，负数为减少
            
        Returns:
            int - 修改后的生命值
        """
        old_health = self.character.health
        self.character.health = max(0, min(self.character.max_health, self.character.health + amount))
        
        logger.info(f"角色 {self.character.name} (ID: {self.character.id}) 的生命值从 {old_health} 变更为 {self.character.health}")
        
        return self.character.health
    
    def set_max_health(self, max_health: int) -> None:
        """设置角色最大生命值
        
        Args:
            max_health: int - 最大生命值
        """
        old_max_health = self.character.max_health
        self.character.max_health = max(1, max_health)
        
        # 如果当前生命值超过新的最大生命值，则调整为最大生命值
        if self.character.health > self.character.max_health:
            self.character.health = self.character.max_health
            
        logger.info(f"角色 {self.character.name} (ID: {self.character.id}) 的最大生命值从 {old_max_health} 变更为 {self.character.max_health}")
    
    def is_alive(self) -> bool:
        """检查角色是否存活
        
        Returns:
            bool - 是否存活
        """
        return self.character.health > 0
    
    def reset_health(self) -> None:
        """重置角色生命值为最大值"""
        old_health = self.character.health
        self.character.health = self.character.max_health
        
        logger.info(f"角色 {self.character.name} (ID: {self.character.id}) 的生命值从 {old_health} 重置为 {self.character.health}")

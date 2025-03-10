import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Match, GameStatus, Character

logger = logging.getLogger(__name__)

class MatchContext:
    """游戏局上下文，提供Match实体的上下文环境"""
    
    def __init__(self, match: Match):
        """初始化游戏局上下文
        
        Args:
            match: Match - 游戏局对象
        """
        self.match = match
        
    def dump_state(self) -> Dict[str, Any]:
        """返回当前状态供Inspector使用
        
        Returns:
            Dict[str, Any]: 游戏局状态
        """
        characters = []
        for character in self.match.characters:
            characters.append({
                "id": character.id,
                "name": character.name,
                "player_id": character.player_id,
                "health": character.health,
                "max_health": character.max_health,
                "attributes": character.attributes
            })
            
        turns = []
        for turn in self.match.turns:
            turn_info = {
                "id": turn.id,
                "turn_type": turn.turn_type,
                "status": turn.status,
                "created_at": turn.created_at.isoformat() if turn.created_at else None,
                "completed_at": turn.completed_at.isoformat() if turn.completed_at else None
            }
            
            # 添加回合类型特有的信息
            if hasattr(turn, 'active_players'):
                turn_info["active_players"] = turn.active_players
                
            if hasattr(turn, 'actions'):
                turn_info["actions"] = turn.actions
                
            if hasattr(turn, 'dice_results'):
                turn_info["dice_results"] = turn.dice_results
                
            if hasattr(turn, 'narration'):
                turn_info["narration"] = turn.narration
                
            if hasattr(turn, 'difficulty'):
                turn_info["difficulty"] = turn.difficulty
                
            if hasattr(turn, 'action_desc'):
                turn_info["action_desc"] = turn.action_desc
                
            turns.append(turn_info)
            
        return {
            "id": self.match.id,
            "scene": self.match.scene,
            "status": self.match.status,
            "scenario_id": self.match.scenario_id,
            "characters": characters,
            "turns": turns,
            "current_turn_id": self.match.current_turn_id,
            "created_at": self.match.created_at.isoformat() if self.match.created_at else None,
            "game_state": self.match.game_state
        }
    
    @classmethod
    def create_match(cls, scenario_id: str = "") -> "MatchContext":
        """创建新的游戏局
        
        Args:
            scene: str - 游戏局场景名称
            
        Returns:
            MatchContext - 新创建的游戏局上下文
        """
        match_id = str(uuid.uuid4())
        new_match = Match(
            id=match_id,
            scenario_id=scenario_id,
            created_at=datetime.now(),
            status=GameStatus.WAITING
        )
        
        logger.info(f"创建新游戏局: ID={match_id}, 名称={scenario_id}")
        
        return cls(new_match)
    
    def start_match(self) -> bool:
        """开始游戏局
        
        Returns:
            bool - 是否成功开始游戏局
        """
        # 检查游戏状态
        if self.match.status == GameStatus.RUNNING:
            logger.warning(f"无法开始游戏局: 当前已有进行中的游戏局 ID={self.match.id}")
            return False
        
        # 检查是否已设置剧本
        if not self.match.scenario_id:
            logger.warning(f"无法开始游戏局: 未设置剧本")
            return False
            
        # 设置游戏状态为运行中
        self.match.status = GameStatus.RUNNING
        logger.info(f"游戏局开始运行: ID={self.match.id}, 状态={self.match.status}")
        
        return True
    
    def end_match(self, result: Optional[str] = None) -> bool:
        """结束游戏局
        
        Args:
            result: Optional[str] - 游戏结果
            
        Returns:
            bool - 是否成功结束游戏局
        """
        # 检查游戏状态
        if self.match.status != GameStatus.RUNNING and self.match.status != GameStatus.PAUSED:
            logger.warning(f"无法结束游戏局: 当前游戏局未在运行中 ID={self.match.id}, 状态={self.match.status}")
            return False
        
        # 设置游戏状态为结束
        self.match.status = GameStatus.FINISHED
        
        # 记录游戏结果
        if result:
            self.match.game_state["result"] = result
            
        logger.info(f"游戏局已结束: ID={self.match.id}, 结果={result or '未知'}")
        
        return True
    
    def pause_match(self) -> bool:
        """暂停游戏局
        
        Returns:
            bool - 是否成功暂停游戏局
        """
        # 检查游戏状态
        if self.match.status != GameStatus.RUNNING:
            logger.warning(f"无法暂停游戏局: 当前游戏局未在运行中 ID={self.match.id}, 状态={self.match.status}")
            return False
        
        # 设置游戏状态为暂停
        self.match.status = GameStatus.PAUSED
        logger.info(f"游戏局已暂停: ID={self.match.id}")
        
        return True
    
    def resume_match(self) -> bool:
        """恢复游戏局
        
        Returns:
            bool - 是否成功恢复游戏局
        """
        # 检查游戏状态
        if self.match.status != GameStatus.PAUSED:
            logger.warning(f"无法恢复游戏局: 当前游戏局未暂停 ID={self.match.id}, 状态={self.match.status}")
            return False
        
        # 设置游戏状态为运行中
        self.match.status = GameStatus.RUNNING
        logger.info(f"游戏局已恢复: ID={self.match.id}")
        
        return True
    
    def set_scenario(self, scenario_id: str) -> bool:
        """设置剧本ID
        
        Args:
            scenario_id: str - 剧本ID
            
        Returns:
            bool - 是否成功设置剧本
        """
        # 检查游戏状态，如果已经开始则不能更换剧本
        if self.match.status == GameStatus.RUNNING:
            logger.warning(f"无法设置剧本: 游戏局已经开始 ID={self.match.id}")
            return False
        
        # 设置剧本ID
        self.match.scenario_id = scenario_id
        logger.info(f"设置剧本: 游戏局ID={self.match.id}, 剧本ID={scenario_id}")
        
        return True
    
    def set_available_characters(self, characters: List[Dict[str, Any]]) -> None:
        """设置可选角色列表
        
        Args:
            characters: List[Dict[str, Any]] - 可选角色列表
        """
        self.match.available_characters = characters
        logger.info(f"设置可选角色列表: 游戏局ID={self.match.id}, 角色数量={len(characters)}")
    
    def add_character(self, character: Character) -> None:
        """添加角色到游戏局
        
        Args:
            character: Character - 角色实体
        """
        self.match.characters.append(character)
        logger.info(f"添加角色到游戏局: 游戏局ID={self.match.id}, 角色ID={character.id}, 角色名称={character.name}")
    
    def remove_character(self, character_id: str) -> Optional[Character]:
        """从游戏局中移除角色
        
        Args:
            character_id: str - 角色ID
            
        Returns:
            Optional[Character] - 被移除的角色，如果角色不存在则返回None
        """
        for i, character in enumerate(self.match.characters):
            if character.id == character_id:
                removed_character = self.match.characters.pop(i)
                logger.info(f"从游戏局中移除角色: 游戏局ID={self.match.id}, 角色ID={character_id}")
                return removed_character
        return None
    
    def get_character(self, character_id: str) -> Optional[Character]:
        """获取角色
        
        Args:
            character_id: str - 角色ID
            
        Returns:
            Optional[Character] - 角色实体，如果不存在则返回None
        """
        for character in self.match.characters:
            if character.id == character_id:
                return character
        return None
    
    def get_character_by_player_id(self, player_id: str) -> Optional[Character]:
        """根据玩家ID获取角色
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[Character] - 角色实体，如果不存在则返回None
        """
        for character in self.match.characters:
            if character.player_id == player_id:
                return character
        return None
    
    def set_current_turn(self, turn_id: Optional[str]) -> None:
        """设置当前回合ID
        
        Args:
            turn_id: Optional[str] - 回合ID，如果为None则清除当前回合
        """
        self.match.current_turn_id = turn_id
        logger.info(f"设置游戏局 {self.match.id} 的当前回合: {turn_id or '无'}")

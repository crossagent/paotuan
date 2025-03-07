import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import uuid
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus
from utils.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)

class MatchManager:
    """游戏局管理器，负责处理与游戏局(Match)相关的所有逻辑"""
    
    def __init__(self, match: Match, room: Room, game_instance):
        """初始化游戏局管理器
        
        Args:
            match: Match - 游戏局对象
            room: Room - 房间对象
            game_instance - 游戏实例
        """
        self.match = match
        self.room = room
        self.game_instance = game_instance
        
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
    def create_match(cls, room: Room, game_instance, name: str = "新的冒险") -> "MatchManager":
        """创建新的游戏局
        
        Args:
            room: Room - 房间对象
            game_instance - 游戏实例
            name: str - 游戏局名称
            
        Returns:
            MatchManager - 新创建的游戏局管理器
        """
        match_id = str(uuid.uuid4())
        new_match = Match(
            id=match_id,
            scene=name,
            created_at=datetime.now(),
            status=GameStatus.WAITING
        )
        
        room.matches.append(new_match)
        room.current_match_id = match_id
        
        logger.info(f"创建新游戏局: ID={match_id}, 名称={name}")
        
        return cls(new_match, room, game_instance)
    
    @classmethod
    def get_current_match_manager(cls, room: Room, game_instance) -> Optional["MatchManager"]:
        """获取房间当前的游戏局管理器
        
        Args:
            room: Room - 房间对象
            game_instance - 游戏实例
            
        Returns:
            Optional[MatchManager] - 当前游戏局管理器，如果没有则返回None
        """
        if not room.current_match_id:
            return None
            
        current_match = None
        for match in room.matches:
            if match.id == room.current_match_id:
                current_match = match
                break
                
        if not current_match:
            return None
            
        return cls(current_match, room, game_instance)
    
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
    
    def set_scenario(self, scenario_id: str) -> Tuple[bool, Optional[str]]:
        """设置剧本
        
        Args:
            scenario_id: str - 剧本ID
            
        Returns:
            Tuple[bool, Optional[str]] - (是否成功设置剧本, 错误消息)
        """
        # 检查游戏状态，如果已经开始则不能更换剧本
        if self.match.status == GameStatus.RUNNING:
            error_msg = f"无法设置剧本: 游戏局已经开始"
            logger.warning(f"{error_msg} ID={self.match.id}")
            return False, error_msg
        
        # 检查剧本是否存在
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        
        if not scenario:
            error_msg = f"无法设置剧本: 剧本不存在 ID={scenario_id}"
            logger.warning(error_msg)
            return False, error_msg
        
        # 检查剧本是否适合当前房间人数
        current_player_count = len(self.room.players)
        room_max_players = getattr(self.room, 'max_players', 6)
        
        # 检查剧本最小玩家数限制
        if current_player_count < scenario.min_players:
            error_msg = f"当前房间人数({current_player_count})不足，该剧本至少需要{scenario.min_players}名玩家"
            logger.warning(f"无法设置剧本: {error_msg}")
            return False, error_msg
        
        # 检查剧本最大玩家数限制
        if room_max_players > scenario.max_players:
            error_msg = f"当前房间最大人数({room_max_players})超过剧本上限，该剧本最多支持{scenario.max_players}名玩家"
            logger.warning(f"无法设置剧本: {error_msg}")
            return False, error_msg
            
        # 设置剧本
        self.match.scenario_id = scenario_id
        
        # 加载角色模板到可选角色列表
        self.match.available_characters = []
        for template in scenario.character_templates:
            self.match.available_characters.append({
                "name": template.name,
                "description": template.description,
                "occupation": template.occupation,
                "is_main": True,
                "attributes": {}
            })
        
        logger.info(f"设置剧本: 游戏局ID={self.match.id}, 剧本ID={scenario_id}")
        
        return True, None
    
    def load_available_characters(self) -> List[Dict[str, Any]]:
        """加载可选角色列表
        
        Returns:
            List[Dict[str, Any]] - 可选角色列表
        """
        if not self.match.scenario_id:
            return []
            
        # 加载剧本
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(self.match.scenario_id)
        
        if not scenario or not hasattr(scenario, 'characters'):
            return []
            
        return scenario.characters
    
    def check_all_players_selected_character(self) -> Tuple[bool, List[str]]:
        """检查所有玩家是否都已选择角色
        
        Returns:
            Tuple[bool, List[str]] - (是否所有玩家都已选择角色, 未选择角色的玩家名称列表)
        """
        players_without_characters = []
        
        for player in self.room.players:
            if not player.character_id:
                players_without_characters.append(player.name)
                
        return len(players_without_characters) == 0, players_without_characters

from typing import Dict, List, Optional, Any
import uuid
import logging
from datetime import datetime

from models.entities import Room, Match, Player, GameStatus, Turn, TurnType, TurnStatus
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent

logger = logging.getLogger(__name__)

class RoomManager:
    """房间管理器"""
    
    def __init__(self, room: Room):
        self.room = room
        
    def set_scenario(self, scenario_id: str) -> bool:
        """设置当前游戏使用的剧本
        
        Args:
            scenario_id: 剧本ID
            
        Returns:
            是否设置成功
        """
        # 获取当前游戏局
        current_match = self.get_current_match()
        if not current_match:
            logger.warning("当前没有游戏局，无法设置剧本")
            return False
            
        # 检查游戏状态，只允许在游戏开始前（WAITING状态）设置剧本
        if current_match.status != GameStatus.WAITING:
            logger.warning(f"无法设置剧本: 游戏已经开始，状态为 {current_match.status}")
            return False
            
        # 加载剧本
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        
        if not scenario:
            logger.warning(f"剧本不存在: {scenario_id}")
            return False
            
        # 更新当前游戏的场景和剧本ID
        current_match.scenario_id = scenario_id
        current_match.scene = scenario.scene
        
        logger.info(f"为房间 {self.room.name} 设置剧本: {scenario.name}")
        return True
        
    def add_player(self, player_id: str, player_name: str) -> Player:
        """添加玩家到房间"""
        # 检查玩家是否已存在
        for player in self.room.players:
            if player.id == player_id:
                logger.info(f"玩家已在房间中: {player_name} (ID: {player_id})")
                return player
                
        # 创建新玩家
        new_player = Player(id=player_id, name=player_name)
        self.room.players.append(new_player)
        logger.info(f"玩家加入房间: {player_name} (ID: {player_id})")
        return new_player
    
    def create_match(self, scene: str) -> Match:
        """创建新游戏局"""
        # 检查是否有进行中的游戏局
        if self.room.current_match_id:
            current_match = self.get_current_match()
            if current_match:
                logger.info(f"检查当前游戏局: ID={current_match.id}, 状态={current_match.status}")
                if current_match.status == GameStatus.RUNNING:
                    logger.warning(f"无法创建新游戏局: 当前已有进行中的游戏局 ID={current_match.id}")
                    raise ValueError("当前已有进行中的游戏局")
                else:
                    logger.info(f"当前游戏局非运行状态，可以创建新游戏局")
                
        # 创建新游戏局
        match_id = str(uuid.uuid4())
        new_match = Match(id=match_id, scene=scene)
        self.room.matches.append(new_match)
        self.room.current_match_id = match_id
        logger.info(f"创建新游戏局: {scene} (ID: {match_id})")
        return new_match
    
    def get_current_match(self) -> Optional[Match]:
        """获取当前游戏局"""
        if not self.room.current_match_id:
            return None
            
        for match in self.room.matches:
            if match.id == self.room.current_match_id:
                return match
                
        return None
        
    def list_players(self) -> List[Player]:
        """列出房间中的所有玩家"""
        return self.room.players

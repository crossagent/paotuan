from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
import logging
import random
from datetime import datetime

from models.entities import Room, Player

logger = logging.getLogger(__name__)

class RoomContext:
    """房间上下文，提供Room实体的上下文环境"""
    
    def __init__(self, room: Room):
        """初始化房间上下文
        
        Args:
            room: Room - 房间实体
        """
        self.room = room
        
    def dump_state(self) -> Dict[str, Any]:
        """返回当前状态供Inspector使用
        
        Returns:
            Dict[str, Any]: 房间状态
        """
        players = []
        for player in self.room.players:
            players.append({
                "id": player.id,
                "name": player.name,
                "is_host": player.is_host,
                "is_ready": player.is_ready,
                "character_id": player.character_id
            })
            
        return {
            "id": self.room.id,
            "name": self.room.name,
            "host_id": self.room.host_id,
            "players": players,
            "current_match_id": self.room.current_match_id,
            "created_at": self.room.created_at.isoformat() if self.room.created_at else None,
            "scenario_id": self.get_scenario_id()
        }
    
    @classmethod
    def create_room(cls, name: str, host_id: Optional[str] = None, default_scenario_id: Optional[str] = None) -> "RoomContext":
        """创建新房间
        
        Args:
            name: str - 房间名称
            host_id: Optional[str] - 房主ID
            default_scenario_id: Optional[str] - 默认剧本ID
            
        Returns:
            RoomContext - 新创建的房间上下文
        """
        room_id = str(uuid.uuid4())
        new_room = Room(
            id=room_id,
            name=name,
            host_id=host_id,
            created_at=datetime.now(),
            settings={"scenario_id": default_scenario_id} if default_scenario_id else {}
        )
        
        logger.info(f"创建新房间: ID={room_id}, 名称={name}, 默认剧本={default_scenario_id or '无'}")
        
        return cls(new_room)
        
    def add_player(self, player_id: str, player_name: str) -> Player:
        """添加玩家到房间
        
        Args:
            player_id: str - 玩家ID
            player_name: str - 玩家名称
            
        Returns:
            Player - 添加的玩家
        """
        # 检查玩家是否已存在
        for player in self.room.players:
            if player.id == player_id:
                logger.info(f"玩家已在房间中: {player_name} (ID: {player_id})")
                return player
                
        # 创建新玩家
        new_player = Player(id=player_id, name=player_name)
        
        # 如果房间为空，设置为房主
        if not self.room.players:
            new_player.is_host = True
            self.room.host_id = player_id
            logger.info(f"设置玩家为房主: {player_name} (ID: {player_id})")
            
        # 添加玩家到房间
        self.room.players.append(new_player)
        
        logger.info(f"玩家加入房间: {player_name} (ID: {player_id})")
        return new_player
        
    def remove_player(self, player_id: str) -> Optional[Player]:
        """将玩家从房间中移除
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[Player] - 被移除的玩家，如果玩家不存在则返回None
        """
        for i, player in enumerate(self.room.players):
            if player.id == player_id:
                removed_player = self.room.players.pop(i)
                
                logger.info(f"玩家离开房间: {removed_player.name} (ID: {player_id})")
                
                return removed_player
                
        return None
    
    def set_current_match(self, match_id: Optional[str]) -> None:
        """设置当前游戏局ID
        
        Args:
            match_id: Optional[str] - 游戏局ID，如果为None则清除当前游戏局
        """
        self.room.current_match_id = match_id
        logger.info(f"设置房间 {self.room.name} (ID: {self.room.id}) 的当前游戏局: {match_id or '无'}")
        
    def list_players(self) -> List[Player]:
        """列出房间中的所有玩家
        
        Returns:
            List[Player] - 玩家列表
        """
        return self.room.players
        
    def set_player_ready(self, player_id: str, is_ready: bool = True) -> bool:
        """设置玩家准备状态
        
        Args:
            player_id: str - 玩家ID
            is_ready: bool - 是否准备
            
        Returns:
            bool - 是否设置成功
        """
        for player in self.room.players:
            if player.id == player_id:
                player.is_ready = is_ready
                logger.info(f"玩家 {player.name} (ID: {player_id}) {'准备完毕' if is_ready else '取消准备'}")
                return True
        return False
        
    def kick_player(self, player_id: str) -> Optional[Player]:
        """房主踢出玩家
        
        Args:
            player_id: str - 要踢出的玩家ID
            
        Returns:
            Optional[Player] - 被踢出的玩家，如果玩家不存在或不能踢出则返回None
        """
        # 检查是否存在该玩家
        player_to_kick = None
        for player in self.room.players:
            if player.id == player_id:
                player_to_kick = player
                break
                
        if not player_to_kick:
            logger.warning(f"踢出失败: 玩家不存在 (ID: {player_id})")
            return None
            
        # 不能踢出房主
        if player_to_kick.is_host:
            logger.warning(f"踢出失败: 不能踢出房主 (ID: {player_id})")
            return None
            
        # 执行踢出操作
        return self.remove_player(player_id)
        
    def assign_new_host(self) -> Optional[Player]:
        """随机选择新房主
        
        Returns:
            Optional[Player] - 新房主，如果没有玩家则返回None
        """
        if not self.room.players:
            self.room.host_id = None
            return None
            
        # 随机选择一名玩家作为新房主
        new_host = random.choice(self.room.players)
        
        # 重置所有玩家的房主状态
        for player in self.room.players:
            player.is_host = (player.id == new_host.id)
            
        # 更新房间的房主ID
        self.room.host_id = new_host.id
        
        logger.info(f"设置新房主: {new_host.name} (ID: {new_host.id})")
        return new_host
        
    def set_host(self, player_id: str) -> bool:
        """设置指定玩家为房主
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            bool - 是否设置成功
        """
        # 检查玩家是否存在
        target_player = None
        for player in self.room.players:
            if player.id == player_id:
                target_player = player
                break
                
        if not target_player:
            logger.warning(f"设置房主失败: 玩家不存在 (ID: {player_id})")
            return False
            
        # 重置所有玩家的房主状态
        for player in self.room.players:
            player.is_host = (player.id == player_id)
            
        # 更新房间的房主ID
        self.room.host_id = player_id
        
        logger.info(f"设置房主: {target_player.name} (ID: {player_id})")
        return True
        
    def are_all_players_ready(self) -> bool:
        """检查是否所有非房主玩家都已准备
        
        Returns:
            bool - 是否所有非房主玩家都已准备
        """
        for player in self.room.players:
            # 跳过房主
            if player.is_host:
                continue
                
            # 如果有玩家未准备，返回False
            if not player.is_ready:
                return False
                
        return True
        
    def get_host(self) -> Optional[Player]:
        """获取当前房主
        
        Returns:
            Optional[Player] - 房主玩家，如果没有则返回None
        """
        if not self.room.host_id:
            return None
            
        for player in self.room.players:
            if player.id == self.room.host_id:
                return player
                
        return None
        
    def set_player_character(self, player_id: str, character_id: Optional[str]) -> bool:
        """设置玩家的角色ID
        
        Args:
            player_id: str - 玩家ID
            character_id: Optional[str] - 角色ID，如果为None则清除角色
            
        Returns:
            bool - 是否设置成功
        """
        for player in self.room.players:
            if player.id == player_id:
                player.character_id = character_id
                logger.info(f"设置玩家 {player.name} (ID: {player_id}) 的角色ID: {character_id or '无'}")
                return True
        return False
        
    def get_player_by_id(self, player_id: str) -> Optional[Player]:
        """根据ID获取玩家
        
        Args:
            player_id: str - 玩家ID
            
        Returns:
            Optional[Player] - 玩家，如果不存在则返回None
        """
        for player in self.room.players:
            if player.id == player_id:
                return player
        return None
        
    def set_scenario(self, scenario_id: str) -> None:
        """设置房间使用的剧本
        
        Args:
            scenario_id: str - 剧本ID
        """
        if 'scenario_id' not in self.room.settings:
            self.room.settings['scenario_id'] = scenario_id
        else:
            self.room.settings['scenario_id'] = scenario_id
        logger.info(f"房间 {self.room.id} 设置剧本: {scenario_id}")
    
    def get_scenario_id(self) -> Optional[str]:
        """获取房间使用的剧本ID
        
        Returns:
            Optional[str] - 剧本ID，如果未设置则返回None
        """
        return self.room.settings.get('scenario_id')

from typing import Dict, List, Optional, Any, Union, Tuple
import uuid
import logging
import random
from datetime import datetime

from models.entities import Room, Match, Player, Character, GameStatus, Turn, TurnType, TurnStatus
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, PlayerLeftEvent

logger = logging.getLogger(__name__)

class RoomManager:
    """房间管理器"""
    
    def __init__(self, room: Room, game_instance=None):
        self.room = room
        self.game_instance = game_instance
        
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
            
        current_match = self.get_current_match()
        current_match_info = None
        if current_match:
            current_match_info = {
                "id": current_match.id,
                "status": current_match.status,
                "scenario_id": current_match.scenario_id,
                "scene": current_match.scene
            }
            
        return {
            "id": self.room.id,
            "name": self.room.name,
            "host_id": self.room.host_id,
            "players": players,
            "current_match": current_match_info,
            "created_at": self.room.created_at.isoformat() if self.room.created_at else None
        }
        
    def set_scenario(self, scenario_id: str) -> Tuple[bool, Optional[str]]:
        """设置当前游戏使用的剧本
        
        Args:
            scenario_id: 剧本ID
            
        Returns:
            Tuple[bool, Optional[str]] - (是否设置成功, 错误消息)
        """
        # 获取当前游戏局
        current_match = self.get_current_match()
        if not current_match:
            error_msg = "当前没有游戏局，无法设置剧本"
            logger.warning(error_msg)
            return False, error_msg
        
        # 使用MatchManager设置剧本
        from core.match import MatchManager
        match_manager = MatchManager(current_match, self.room, self.game_instance)
        success, error_msg = match_manager.set_scenario(scenario_id)
        
        if not success:
            logger.warning(f"设置剧本失败: {error_msg}")
            return False, error_msg
            
        logger.info(f"为房间 {self.room.name} 设置剧本: {scenario_id}")
        return True, None
        
    def add_player(self, player_id: str, player_name: str) -> Player:
        """添加玩家到房间"""
        # 检查玩家是否已存在
        for player in self.room.players:
            if player.id == player_id:
                logger.info(f"玩家已在房间中: {player_name} (ID: {player_id})")
                # 确保玩家-房间映射存在
                if self.game_instance:
                    self.game_instance.player_room_map[player_id] = self.room.id
                return player
                
        # 创建新玩家，但不创建角色
        new_player = Player(id=player_id, name=player_name)
        
        # 如果房间为空，设置为房主
        if not self.room.players:
            new_player.is_host = True
            self.room.host_id = player_id
            logger.info(f"设置玩家为房主: {player_name} (ID: {player_id})")
            
        # 添加玩家到房间
        self.room.players.append(new_player)
        
        # 更新玩家-房间映射
        if self.game_instance:
            self.game_instance.player_room_map[player_id] = self.room.id
            
        logger.info(f"玩家加入房间: {player_name} (ID: {player_id})")
        return new_player
        
    def remove_player(self, player_id: str) -> Tuple[bool, Optional[PlayerLeftEvent]]:
        """将玩家从房间中移除
        
        Args:
            player_id: 玩家ID
            
        Returns:
            (是否成功移除玩家, 玩家离开事件)
        """
        for i, player in enumerate(self.room.players):
            if player.id == player_id:
                removed_player = self.room.players.pop(i)
                player_name = removed_player.name
                was_host = removed_player.is_host
                character_id = removed_player.character_id
                
                # 从当前游戏局中移除对应的角色
                current_match = self.get_current_match()
                if current_match and character_id:
                    for j, character in enumerate(current_match.characters):
                        if character.id == character_id:
                            current_match.characters.pop(j)
                            logger.info(f"从游戏局中移除角色: ID={character_id}")
                            break
                
                # 从映射中移除
                if self.game_instance and player_id in self.game_instance.player_room_map:
                    del self.game_instance.player_room_map[player_id]
                
                # 从角色映射中移除
                if self.game_instance and player_id in self.game_instance.player_character_map:
                    del self.game_instance.player_character_map[player_id]
                
                logger.info(f"玩家离开房间: {player_name} (ID: {player_id})")
                
                # 如果是房主且房间还有其他玩家，选择新房主
                if was_host and self.room.players:
                    self.assign_new_host()
                
                # 如果房间为空，返回房间应该被关闭的信息
                if not self.room.players:
                    logger.info(f"房间已空: {self.room.name} (ID: {self.room.id})")
                    return True, PlayerLeftEvent(
                        player_id=player_id,
                        player_name=player_name,
                        room_id=self.room.id,
                        room_empty=True
                    )
                
                return True, PlayerLeftEvent(
                    player_id=player_id,
                    player_name=player_name,
                    room_id=self.room.id,
                    room_empty=False
                )
        return False, None
    
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
        
    def broadcast_to_room(self, message: str, exclude_players: List[str] = None) -> List[Dict[str, str]]:
        """向房间中所有玩家广播消息
        
        Args:
            message: 要广播的消息内容
            exclude_players: 要排除的玩家ID列表
            
        Returns:
            消息列表，每个消息包含recipient和content
        """
        exclude_players = exclude_players or []
        messages = []
        for player in self.room.players:
            if player.id not in exclude_players:
                messages.append({"recipient": player.id, "content": message})
        return messages
        
    def set_player_ready(self, player_id: str, is_ready: bool = True) -> bool:
        """设置玩家准备状态
        
        Args:
            player_id: 玩家ID
            is_ready: 是否准备
            
        Returns:
            是否设置成功
        """
        for player in self.room.players:
            if player.id == player_id:
                player.is_ready = is_ready
                logger.info(f"玩家 {player.name} (ID: {player_id}) {'准备完毕' if is_ready else '取消准备'}")
                return True
        return False
        
    def kick_player(self, player_id: str) -> Tuple[bool, Optional[PlayerLeftEvent]]:
        """房主踢出玩家
        
        Args:
            player_id: 要踢出的玩家ID
            
        Returns:
            (是否成功踢出, 玩家离开事件)
        """
        # 检查是否存在该玩家
        player_to_kick = None
        for player in self.room.players:
            if player.id == player_id:
                player_to_kick = player
                break
                
        if not player_to_kick:
            logger.warning(f"踢出失败: 玩家不存在 (ID: {player_id})")
            return False, None
            
        # 不能踢出房主
        if player_to_kick.is_host:
            logger.warning(f"踢出失败: 不能踢出房主 (ID: {player_id})")
            return False, None
            
        # 执行踢出操作
        return self.remove_player(player_id)
        
    def assign_new_host(self) -> Optional[Player]:
        """随机选择新房主
        
        Returns:
            新房主，如果没有玩家则返回None
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
            player_id: 玩家ID
            
        Returns:
            是否设置成功
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
            是否所有非房主玩家都已准备
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
            房主玩家，如果没有则返回None
        """
        if not self.room.host_id:
            return None
            
        for player in self.room.players:
            if player.id == self.room.host_id:
                return player
                
        return None
        
    def get_character_by_player_id(self, player_id: str) -> Optional[Character]:
        """根据玩家ID获取对应的角色
        
        Args:
            player_id: 玩家ID
            
        Returns:
            玩家对应的角色，如果找不到则返回None
        """
        # 先找到玩家
        player = None
        for p in self.room.players:
            if p.id == player_id:
                player = p
                break
                
        if not player or not player.character_id:
            return None
            
        # 获取当前游戏局
        current_match = self.get_current_match()
        if not current_match:
            return None
            
        # 根据character_id从当前游戏局中找到对应的角色
        for character in current_match.characters:
            if character.id == player.character_id:
                return character
                
        return None
        
    def select_character(self, player_id: str, character_name: str) -> Tuple[bool, str]:
        """玩家选择角色
        
        Args:
            player_id: 玩家ID
            character_name: 角色名称
            
        Returns:
            (是否选择成功, 消息)
        """
        # 获取当前游戏局
        current_match = self.get_current_match()
        if not current_match:
            return False, "当前没有游戏局，无法选择角色"
            
        # 检查游戏状态，只允许在游戏开始前（WAITING状态）选择角色
        if current_match.status != GameStatus.WAITING:
            return False, "游戏已经开始，无法更换角色"
            
        # 检查剧本是否已设置
        if not current_match.scenario_id:
            return False, "请先设置剧本再选择角色"
            
        # 检查可选角色列表是否为空
        if not current_match.available_characters:
            return False, "当前剧本没有可选角色"
            
        # 查找玩家
        player = None
        for p in self.room.players:
            if p.id == player_id:
                player = p
                break
                
        if not player:
            return False, "找不到玩家"
            
        # 查找角色
        selected_character_info = None
        for char_info in current_match.available_characters:
            if char_info.get("name") == character_name:
                selected_character_info = char_info
                break
                
        if not selected_character_info:
            available_chars = ", ".join([c.get("name", "未知") for c in current_match.available_characters])
            return False, f"找不到角色: {character_name}。可选角色: {available_chars}"
            
        # 检查角色是否已被选择
        for character in current_match.characters:
            if character.name == character_name and character.player_id is not None:
                return False, f"角色 {character_name} 已被其他玩家选择"
                
        # 如果玩家已有角色，先解除绑定
        if player.character_id:
            for character in current_match.characters:
                if character.id == player.character_id:
                    character.player_id = None
                    logger.info(f"解除玩家 {player.name} 与角色 {character.name} 的绑定")
                    break
                    
        # 创建新角色或使用现有角色
        character_exists = False
        for character in current_match.characters:
            if character.name == character_name and character.player_id is None:
                character.player_id = player_id
                player.character_id = character.id
                character_exists = True
                logger.info(f"玩家 {player.name} 选择了现有角色 {character_name}")
                break
                
        if not character_exists:
            # 创建新角色
            character_id = str(uuid.uuid4())
            new_character = Character(
                id=character_id,
                name=character_name,
                player_id=player_id,
                attributes=selected_character_info.get("attributes", {})
            )
            
            # 添加角色到游戏局
            current_match.characters.append(new_character)
            
            # 关联玩家和角色
            player.character_id = character_id
            
            logger.info(f"玩家 {player.name} 选择了角色 {character_name}，创建角色ID: {character_id}")
            
        # 更新玩家-角色映射
        if self.game_instance:
            self.game_instance.player_character_map[player_id] = player.character_id
            
        return True, f"成功选择角色: {character_name}"
        
    def load_available_characters(self) -> List[Dict[str, Any]]:
        """从剧本中加载可选角色列表
        
        Returns:
            可选角色列表
        """
        # 获取当前游戏局
        current_match = self.get_current_match()
        if not current_match or not current_match.scenario_id:
            logger.warning("当前没有游戏局或未设置剧本，无法加载可选角色")
            return []
            
        # 加载剧本
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(current_match.scenario_id)
        
        if not scenario:
            logger.warning(f"剧本不存在: {current_match.scenario_id}")
            return []
            
        # 提取角色信息
        available_characters = []
        
        # 添加主要角色
        if hasattr(scenario, "characters") and scenario.characters:
            for char in scenario.characters:
                if hasattr(char, "name") and char.name:
                    available_characters.append({
                        "name": char.name,
                        "description": getattr(char, "description", ""),
                        "is_main": getattr(char, "is_main", True),
                        "attributes": {}
                    })
        
        # 如果没有角色，尝试从重要角色中提取
        if not available_characters and hasattr(scenario, "important_characters"):
            for char_type, chars in scenario.important_characters.items():
                for char in chars:
                    if isinstance(char, dict) and "角色名称" in char:
                        available_characters.append({
                            "name": char["角色名称"],
                            "description": char.get("描述", ""),
                            "is_main": char_type == "主要角色",
                            "attributes": {}
                        })
        
        # 更新游戏局的可选角色列表
        if current_match:
            current_match.available_characters = available_characters
            logger.info(f"为游戏局 {current_match.id} 加载了 {len(available_characters)} 个可选角色")
            
        return available_characters

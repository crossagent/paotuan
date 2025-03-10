from typing import Dict, List, Optional, Any, Union
import json
import logging
from datetime import datetime
from models.entities import Room, Match, Player, Turn, BaseTurn, DMTurn, ActionTurn, DiceTurn, GameStatus, TurnType, TurnStatus

class GameStateInspector:
    """游戏状态检查器，提供查询游戏状态的功能"""
    
    def __init__(self, game_state=None):
        self.game_state = game_state
        self.logger = logging.getLogger("game_inspector")
        
    def dump_all_state(self, room_id=None) -> Dict[str, Any]:
        """导出所有状态信息"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "rooms": []
        }
        
        if not self.game_state:
            return result
            
        rooms = self.game_state.rooms
        
        # 如果指定了房间ID，只导出该房间
        if room_id and room_id in rooms:
            room_data = self._format_room(rooms[room_id])
            result["rooms"].append(room_data)
        else:
            # 导出所有房间
            for room in rooms.values():
                room_data = self._format_room(room)
                result["rooms"].append(room_data)
                
        return result
    
    def dump_room_state(self, room_id) -> Dict[str, Any]:
        """导出房间状态"""
        if not self.game_state or not room_id:
            return {}
            
        room = self.game_state.get_room(room_id)
        if not room:
            return {"error": f"房间不存在: {room_id}"}
            
        return self._format_room(room)
    
    def dump_match_state(self, room_id) -> Dict[str, Any]:
        """导出当前比赛状态"""
        if not self.game_state or not room_id:
            return {}
            
        room = self.game_state.get_room(room_id)
        if not room or not room.current_match_id:
            return {"error": "没有进行中的比赛"}
            
        for match in room.matches:
            if match.id == room.current_match_id:
                return self._format_match(match)
                
        return {"error": "比赛数据不一致"}
    
    def dump_current_turn(self, room_id) -> Dict[str, Any]:
        """导出当前回合状态"""
        match_data = self.dump_match_state(room_id)
        if "error" in match_data:
            return match_data
            
        if not match_data.get("current_turn_id"):
            return {"error": "没有活动回合"}
            
        for turn in match_data.get("turns", []):
            if turn["id"] == match_data["current_turn_id"]:
                return turn
                
        return {"error": "回合数据不一致"}
    
    def dump_players(self, room_id) -> List[Dict[str, Any]]:
        """导出玩家状态"""
        if not self.game_state or not room_id:
            return []
            
        room = self.game_state.get_room(room_id)
        if not room:
            return [{"error": f"房间不存在: {room_id}"}]
            
        return [self._format_player(player) for player in room.players]
    
    def _format_room(self, room: Room) -> Dict[str, Any]:
        """格式化房间数据"""
        return {
            "id": room.id,
            "name": room.name,
            "created_at": room.created_at.isoformat(),
            "players": [self._format_player(p) for p in room.players],
            "current_match_id": room.current_match_id,
            "matches": [self._format_match(m) for m in room.matches],
            "settings": room.settings
        }
    
    def _format_match(self, match: Match) -> Dict[str, Any]:
        """格式化比赛数据"""
        return {
            "id": match.id,
            "status": match.status,
            "scene": match.scene,
            "created_at": match.created_at.isoformat(),
            "current_turn_id": match.current_turn_id,
            "turns": [self._format_turn(t) for t in match.turns],
            "game_state": match.game_state
        }
    
    def _format_turn(self, turn: Union[BaseTurn, DMTurn, ActionTurn, DiceTurn]) -> Dict[str, Any]:
        """格式化回合数据"""
        # 处理next_turn_info，如果存在则转换为字典
        next_turn_info = None
        if turn.next_turn_info:
            next_turn_info = {
                "turn_type": turn.next_turn_info.turn_type,
                "active_players": turn.next_turn_info.active_players
            }
        
        # 基础回合数据
        result = {
            "id": turn.id,
            "turn_type": turn.turn_type,
            "status": turn.status,
            "created_at": turn.created_at.isoformat(),
            "completed_at": turn.completed_at.isoformat() if turn.completed_at else None,
            "next_turn_info": next_turn_info
        }
        
        # 根据回合类型添加特定字段
        if isinstance(turn, DMTurn):
            result["narration"] = turn.narration
        
        elif isinstance(turn, ActionTurn):
            result["active_players"] = turn.active_players
            result["actions"] = turn.actions
            result["turn_mode"] = "action"
        
        elif isinstance(turn, DiceTurn):
            result["active_players"] = turn.active_players
            result["turn_mode"] = "dice"
            result["difficulty"] = turn.difficulty
            result["action_desc"] = turn.action_desc
            result["dice_results"] = turn.dice_results
        
        # 兼容旧版Turn类型
        elif hasattr(turn, 'active_players'):
            result["active_players"] = turn.active_players
            result["actions"] = getattr(turn, 'actions', {})
            result["turn_mode"] = getattr(turn, 'turn_mode', None)
            result["difficulty"] = getattr(turn, 'difficulty', None)
            result["dice_results"] = getattr(turn, 'dice_results', {})
            
        return result
    
    def _format_player(self, player: Player) -> Dict[str, Any]:
        """格式化玩家数据"""
        result = {
            "id": player.id,
            "name": player.name,
            "joined_at": player.joined_at.isoformat(),
            "is_ready": player.is_ready,
            "is_host": player.is_host,
            "character_id": player.character_id,
            # 添加默认的角色属性，确保前端不会因缺少这些字段而出错
            "health": 0,
            "alive": False,
            "attributes": {},
            "items": [],
            "location": None
        }
        
        # 如果有游戏状态，尝试查找关联的角色信息
        if self.game_state and player.character_id:
            # 直接使用game_state中的player_character_map查找角色ID
            character_id = player.character_id
            
            # 查找当前房间
            room_id = self.game_state.player_room_map.get(player.id)
            if room_id:
                room = self.game_state.get_room(room_id)
                if room and room.current_match_id:
                    match = next((m for m in room.matches if m.id == room.current_match_id), None)
                    if match:
                        character = next((c for c in match.characters if c.id == character_id), None)
                        if character:
                            # 添加角色信息
                            result.update(self._format_character(character))
                            self.logger.debug(f"找到玩家 {player.name} 的角色信息")
                        else:
                            self.logger.debug(f"未找到玩家 {player.name} 的角色信息，character_id={character_id}")
        
        return result
    
    def _format_character(self, character) -> Dict[str, Any]:
        """格式化角色数据"""
        return {
            "health": character.health,
            "alive": character.alive,
            "attributes": character.attributes,
            "items": character.items,
            "location": character.location
        }

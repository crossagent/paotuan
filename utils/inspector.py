from typing import Dict, List, Optional, Any, Union
import json
import logging
from datetime import datetime
from models.entities import Room, Match, Player, Turn, BaseTurn, DMTurn, ActionTurn, DiceTurn, GameStatus, TurnType, TurnStatus

class GameStateInspector:
    """游戏状态检查器，提供查询游戏状态的功能"""
    
    def __init__(self, game_instance=None):
        self.game_instance = game_instance
        self.logger = logging.getLogger("game_inspector")
        
    def dump_all_state(self, room_id=None) -> Dict[str, Any]:
        """导出所有状态信息"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "rooms": []
        }
        
        if not self.game_instance:
            return result
            
        rooms = self.game_instance.rooms
        
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
        if not self.game_instance or not room_id:
            return {}
            
        room = self.game_instance.get_room(room_id)
        if not room:
            return {"error": f"房间不存在: {room_id}"}
            
        return self._format_room(room)
    
    def dump_match_state(self, room_id) -> Dict[str, Any]:
        """导出当前比赛状态"""
        if not self.game_instance or not room_id:
            return {}
            
        room = self.game_instance.get_room(room_id)
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
        if not self.game_instance or not room_id:
            return []
            
        room = self.game_instance.get_room(room_id)
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
        return {
            "id": player.id,
            "name": player.name,
            "joined_at": player.joined_at.isoformat(),
            "health": player.health,
            "alive": player.alive,
            "attributes": player.attributes,
            "items": player.items
        }

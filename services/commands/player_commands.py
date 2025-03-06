import logging
from typing import List, Dict, Any, Optional, Union

from models.entities import Room, Match, Player, Character, TurnType, TurnStatus, GameStatus, DiceTurn
from core.room import RoomManager
from core.turn import TurnManager
from adapters.base import GameEvent, PlayerJoinedEvent, PlayerActionEvent, DMNarrationEvent, SelectCharacterEvent
from services.commands.base import GameCommand

logger = logging.getLogger(__name__)

class PlayerJoinedCommand(GameCommand):
    """处理玩家加入事件的命令"""
    
    async def execute(self, event: PlayerJoinedEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        player_name = event.data["player_name"]
        
        logger.info(f"处理玩家加入事件: 玩家={player_name}({player_id})")
        
        # 获取所有房间
        rooms = self.game_instance.list_rooms()
        
        # 如果没有房间，创建一个默认房间
        if not rooms:
            room = self.game_instance.create_room("默认房间")
            room_manager = RoomManager(room, self.game_instance)
            player = room_manager.add_player(player_id, player_name)
            
            logger.info(f"创建默认房间并添加玩家: {player_name}({player_id}), 房间={room.name}")
            
            return [{"recipient": player_id, "content": f"已创建默认房间并加入: {room.name} (ID: {room.id})"}]
        
        # 如果有多个房间，返回房间列表让玩家选择
        if len(rooms) > 1:
            rooms_msg = "当前有多个房间可用，请选择一个加入:\n"
            for room in rooms:
                # 获取房间状态
                current_match = None
                for match in room.matches:
                    if match.id == room.current_match_id:
                        current_match = match
                        break
                        
                status = "等待中"
                if current_match:
                    if current_match.status == GameStatus.RUNNING:
                        status = "游戏中"
                    elif current_match.status == GameStatus.PAUSED:
                        status = "已暂停"
                    elif current_match.status == GameStatus.FINISHED:
                        status = "已结束"
                
                rooms_msg += f"- {room.name} (ID: {room.id})\n"
                rooms_msg += f"  状态: {status}, 玩家数: {len(room.players)}\n"
            
            rooms_msg += "\n使用 /加入房间 [房间ID] 加入指定房间"
            
            logger.info(f"向玩家发送房间列表: {player_name}({player_id})")
            
            return [{"recipient": player_id, "content": rooms_msg}]
        
        # 如果只有一个房间，直接加入
        room = rooms[0]
        room_manager = RoomManager(room, self.game_instance)
        player = room_manager.add_player(player_id, player_name)
        
        logger.info(f"玩家加入唯一房间: {player_name}({player_id}), 房间={room.name}")
        
        return [{"recipient": player_id, "content": f"你已成功加入房间: {room.name} (ID: {room.id})"}]


class PlayerActionCommand(GameCommand):
    """处理玩家行动事件的命令"""
    
    async def execute(self, event: PlayerActionEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        action = event.data["action"]
        
        # 查找玩家所在的房间 - 使用辅助方法
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 获取玩家对应的角色
        character = room_manager.get_character_by_player_id(player_id)
        if not character:
            return [{"recipient": player_id, "content": "找不到你的游戏角色，请尝试重新加入房间"}]
        
        # 检查是否有进行中的游戏局
        match = room_manager.get_current_match()
        if not match:
            return [{"recipient": player_id, "content": "当前没有进行中的游戏局"}]
            
        # 获取回合管理器
        turn_manager = TurnManager(match)
        current_turn = turn_manager.get_current_turn()
        
        # 检查是否有活动回合
        if not current_turn:
            return [{"recipient": player_id, "content": "当前没有活动回合"}]
            
        # 检查是否是玩家回合
        if current_turn.turn_type != TurnType.PLAYER:
            return []
            
        # 处理玩家行动
        success = turn_manager.handle_player_action(player_id, action)
        if not success:
            return [{"recipient": player_id, "content": "无法处理你的行动"}]
            
        # 检查回合是否完成
        if current_turn.status != TurnStatus.COMPLETED:
            return []
            
        # 如果是掷骰子回合，处理掷骰子结果
        messages = []
        if isinstance(current_turn, DiceTurn):
            # 处理掷骰子结果
            dice_results = self.rule_engine.process_dice_turn_results(current_turn)
            
            # 通知所有玩家掷骰子结果
            result_message = "【掷骰子结果】\n"
            for result in dice_results.get("summary", []):
                player_name = next((p.name for p in player_room.players if p.id == result["player_id"]), result["player_id"])
                result_message += f"{player_name} 尝试 {result['action']}，掷出了 {result['roll']}，难度 {result['difficulty']}，{'成功' if result['success'] else '失败'}\n"
            
            for pid in [p.id for p in player_room.players]:
                messages.append({"recipient": pid, "content": result_message})
        
        # 转到DM回合
        turn_manager.complete_current_turn(TurnType.DM)
        
        # 创建DM回合
        dm_turn = turn_manager.start_new_turn(TurnType.DM)
        
        # 触发DM叙述，传入房间ID
        messages.append(DMNarrationEvent("", player_room.id))
        
        return messages


class SelectCharacterCommand(GameCommand):
    """处理选择角色事件的命令"""
    
    async def execute(self, event: SelectCharacterEvent) -> List[Union[GameEvent, Dict[str, str]]]:
        player_id = event.data["player_id"]
        character_name = event.data["character_name"]
        
        logger.info(f"处理选择角色事件: 玩家ID={player_id}, 角色名称={character_name}")
        
        # 查找玩家所在的房间
        player_room = self._get_player_room(player_id)
                
        # 如果找不到玩家所在的房间，提示玩家加入房间
        if not player_room:
            return [{"recipient": player_id, "content": "你尚未加入任何房间，请先使用 /加入游戏 或 /加入房间 [房间ID] 加入房间"}]
        
        # 创建房间管理器
        room_manager = RoomManager(player_room, self.game_instance)
        
        # 选择角色
        success, message = room_manager.select_character(player_id, character_name)
        
        # 查找玩家名称
        player_name = "未知玩家"
        for p in player_room.players:
            if p.id == player_id:
                player_name = p.name
                break
        
        if success:
            # 通知所有玩家
            messages = []
            for p in player_room.players:
                if p.id != player_id:  # 不通知选择角色的玩家自己
                    messages.append({"recipient": p.id, "content": f"玩家 {player_name} 选择了角色: {character_name}"})
            
            # 通知选择角色的玩家
            messages.append({"recipient": player_id, "content": message})
            return messages
        else:
            # 选择失败，只通知选择角色的玩家
            return [{"recipient": player_id, "content": message}]

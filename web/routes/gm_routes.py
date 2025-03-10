from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
import logging
import uuid
from datetime import datetime
import os

from web.routes.user_routes import get_current_user
from web.auth import User
from models.entities import Room, Match, Player, Character, GameStatus, TurnType, TurnStatus, BaseTurn, DMTurn, ActionTurn, DiceTurn, NextTurnInfo
from services.ai_service import OpenAIService

# 创建路由器
router = APIRouter(
    prefix="/api/debug",
    tags=["debug"],
    responses={404: {"description": "Not found"}},
)

# 配置日志
logger = logging.getLogger(__name__)

# 全局服务引用
game_state_service = None
room_service = None
match_service = None
turn_service = None
event_bus = None
ai_service = None

# 设置游戏状态
def set_game_state(game_state):
    global game_state_service, room_service, match_service, turn_service, event_bus
    from services.game_state_service import GameStateService
    from services.room_service import RoomService
    from services.match_service import MatchService
    from services.turn_service import TurnService
    from core.events import EventBus
    
    # 创建服务
    event_bus = EventBus()
    game_state_service = GameStateService(game_state, event_bus)
    room_service = RoomService(game_state_service, event_bus)
    match_service = MatchService(game_state_service, event_bus)
    turn_service = TurnService(game_state_service, event_bus)

# 重置游戏状态
@router.post("/reset", response_model=Dict[str, Any])
async def reset_game_state(current_user: User = Depends(get_current_user)):
    """重置游戏状态，清空所有房间和游戏"""
    if not game_state_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    # 清空房间
    game_state_service.game_state.rooms = {}
    game_state_service.game_state.player_room_map = {}
    game_state_service.game_state.player_character_map = {}
    
    logger.info(f"游戏状态已重置，所有房间和游戏已清空")
    
    return {
        "success": True,
        "message": "游戏状态已重置"
    }

# 获取游戏状态
@router.get("/game_state", response_model=Dict[str, Any])
async def get_debug_game_state(current_user: User = Depends(get_current_user)):
    """获取完整的游戏状态，包括所有房间、游戏和玩家信息"""
    if not game_state_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    rooms = []
    for room in game_state_service.list_rooms():
        room_info = {
            "id": room.id,
            "name": room.name,
            "created_at": room.created_at,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "is_ready": p.is_ready,
                    "is_host": p.is_host,
                    "character_id": p.character_id
                } for p in room.players
            ],
            "current_match_id": room.current_match_id,
            "matches": []
        }
        
        for match in room.matches:
            match_info = {
                "id": match.id,
                "status": match.status,
                "scene": match.scene,
                "created_at": match.created_at,
                "scenario_id": match.scenario_id,
                "current_turn_id": match.current_turn_id,
                "characters": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "player_id": c.player_id,
                        "health": c.health,
                        "alive": c.alive,
                        "location": c.location
                    } for c in match.characters
                ],
                "turns": []
            }
            
            for turn in match.turns:
                turn_info = {
                    "id": turn.id,
                    "turn_type": turn.turn_type,
                    "status": turn.status,
                    "created_at": turn.created_at,
                    "completed_at": turn.completed_at
                }
                
                if turn.turn_type == TurnType.DM:
                    turn_info["narration"] = turn.narration
                    if turn.next_turn_info:
                        turn_info["next_turn_info"] = {
                            "turn_type": turn.next_turn_info.turn_type,
                            "active_players": turn.next_turn_info.active_players
                        }
                
                elif hasattr(turn, "active_players"):
                    turn_info["active_players"] = turn.active_players
                    
                    if hasattr(turn, "actions"):
                        turn_info["actions"] = turn.actions
                    
                    if hasattr(turn, "difficulty"):
                        turn_info["difficulty"] = turn.difficulty
                        turn_info["action_desc"] = turn.action_desc
                        turn_info["dice_results"] = turn.dice_results
                
                match_info["turns"].append(turn_info)
            
            room_info["matches"].append(match_info)
        
        rooms.append(room_info)
    
    return {
        "rooms": rooms,
        "player_room_map": game_state_service.game_state.player_room_map,
        "player_character_map": game_state_service.game_state.player_character_map
    }

# 模拟玩家行动
@router.post("/simulate_player_action", response_model=Dict[str, Any])
async def simulate_player_action(
    action_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """模拟玩家行动，可以指定玩家ID、行动内容等"""
    if not game_state_service or not turn_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_id = action_data.get("room_id")
    if not room_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定房间ID"
        )
    
    room = game_state_service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    if not room.current_match_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="房间没有进行中的游戏"
        )
    
    # 获取当前游戏局
    match = next((m for m in room.matches if m.id == room.current_match_id), None)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏不存在"
        )
    
    if not match.current_turn_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏没有当前回合"
        )
    
    # 获取当前回合
    turn = next((t for t in match.turns if t.id == match.current_turn_id), None)
    if not turn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回合不存在"
        )
    
    if turn.turn_type != TurnType.PLAYER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不是玩家回合"
        )
    
    player_id = action_data.get("player_id")
    if not player_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须指定玩家ID"
        )
    
    # 检查玩家是否在活跃列表中
    if hasattr(turn, "active_players") and player_id not in turn.active_players:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该玩家不在当前回合的活跃玩家列表中"
        )
    
    action_text = action_data.get("action", "这是一个测试行动")
    
    # 根据回合类型处理行动
    if hasattr(turn, "difficulty"):  # DiceTurn
        from core.contexts.turn_context import TurnContext
        turn_controller = TurnContext(turn)
        
        # 模拟掷骰子
        roll = action_data.get("roll")
        if roll is None:
            import random
            roll = random.randint(1, 20)
        
        success = roll >= turn.difficulty
        
        # 记录掷骰结果
        turn_controller.record_dice_result(player_id, {
            "roll": roll,
            "success": success,
            "difficulty": turn.difficulty,
            "action": action_text
        })
        
        result = {
            "player_id": player_id,
            "action": action_text,
            "roll": roll,
            "difficulty": turn.difficulty,
            "success": success
        }
    else:  # ActionTurn
        from core.contexts.turn_context import TurnContext
        turn_controller = TurnContext(turn)
        
        # 记录行动
        turn_controller.record_action(player_id, action_text)
        
        result = {
            "player_id": player_id,
            "action": action_text
        }
    
    # 检查是否所有活跃玩家都已行动
    all_acted = True
    if hasattr(turn, "active_players"):
        if hasattr(turn, "actions"):
            for p_id in turn.active_players:
                if p_id not in turn.actions:
                    all_acted = False
                    break
        elif hasattr(turn, "dice_results"):
            for p_id in turn.active_players:
                if p_id not in turn.dice_results:
                    all_acted = False
                    break
    
    # 如果所有玩家都已行动，完成回合
    if all_acted:
        turn.status = TurnStatus.COMPLETED
        turn.completed_at = datetime.now()
    
    logger.info(f"模拟玩家行动: 玩家={player_id}, 行动={action_text}, 回合={turn.id}")
    
    return {
        "success": True,
        "result": result,
        "turn_completed": turn.status == TurnStatus.COMPLETED,
        "all_players_acted": all_acted
    }

# 设置AI提示模板
@router.post("/set_ai_prompt", response_model=Dict[str, Any])
async def set_ai_prompt(
    prompt_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """设置AI提示模板，可以指定使用哪个prompt文件"""
    global ai_service
    
    prompt_type = prompt_data.get("prompt_type", "default")
    
    # 确定prompt文件路径
    if prompt_type == "test":
        prompt_path = "ai/prompts/test_prompt.txt"
    else:
        prompt_path = "ai/prompts/default_prompt.txt"
    
    # 检查文件是否存在
    if not os.path.exists(prompt_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"提示模板文件 {prompt_path} 不存在"
        )
    
    # 创建或重新初始化AI服务
    try:
        ai_service = OpenAIService(prompt_path=prompt_path)
        logger.info(f"AI提示模板已切换为 {prompt_type} 模式，使用文件: {prompt_path}")
        
        return {
            "success": True,
            "message": f"AI提示模板已切换为 {prompt_type} 模式",
            "prompt_path": prompt_path
        }
    except Exception as e:
        logger.exception(f"设置AI提示模板失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"设置AI提示模板失败: {str(e)}"
        )

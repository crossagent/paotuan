from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
import logging
import uuid
from datetime import datetime

from web.routes.user_routes import get_current_user
from web.auth import User
from models.entities import Room, Match, Player, Character, GameStatus, TurnType, TurnStatus, BaseTurn, DMTurn, ActionTurn, DiceTurn, NextTurnInfo

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
    game_state_service.game_state.rooms = []
    game_state_service.game_state.player_room_map = {}
    game_state_service.game_state.player_character_map = {}
    
    logger.info(f"游戏状态已重置，所有房间和游戏已清空")
    
    return {
        "success": True,
        "message": "游戏状态已重置"
    }

# 创建测试房间
@router.post("/create_test_room", response_model=Dict[str, Any])
async def create_test_room(
    room_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """创建测试房间，可以指定房间名称、玩家数量等"""
    if not game_state_service or not room_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_name = room_data.get("name", "测试房间")
    player_count = room_data.get("player_count", 3)
    all_ready = room_data.get("all_ready", False)
    
    # 创建房间
    from core.controllers.room_controller import RoomController
    
    # 使用RoomService创建房间
    room_controller, messages = await room_service.create_room(room_name, current_user.id)
    room = room_controller.room
    
    # 添加测试玩家
    for i in range(1, player_count):
        player_id = f"test_player_{i}"
        player_name = f"测试玩家{i}"
        player = Player(id=player_id, name=player_name, is_ready=all_ready)
        room_controller.add_player(player)
        game_state_service.register_player_room(player_id, room.id)
    
    logger.info(f"创建测试房间: {room_name} (ID: {room.id}), 玩家数量: {player_count}, 全部准备: {all_ready}")
    
    return {
        "id": room.id,
        "name": room.name,
        "player_count": len(room.players),
        "players": [{"id": p.id, "name": p.name, "is_ready": p.is_ready} for p in room.players]
    }

# 创建测试游戏
@router.post("/create_test_game", response_model=Dict[str, Any])
async def create_test_game(
    game_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """在指定房间中创建测试游戏，可以指定剧本、场景等"""
    if not game_state_service or not room_service or not match_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_id = game_data.get("room_id")
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
    
    scenario_id = game_data.get("scenario_id", "asylum")
    scene = game_data.get("scene", "默认场景")
    game_status = game_data.get("status", GameStatus.RUNNING)
    
    # 创建新游戏局
    match_id = str(uuid.uuid4())
    match = Match(id=match_id, room_id=room.id, scene=scene, created_at=datetime.now(), status=game_status)
    
    # 设置剧本
    if scenario_id:
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"剧本不存在: {scenario_id}"
            )
        match.scenario_id = scenario_id
    
    # 添加到房间
    room.matches.append(match)
    room.current_match_id = match_id
    
    # 为每个玩家创建角色
    for i, player in enumerate(room.players):
        character_id = str(uuid.uuid4())
        character_name = f"角色{i+1}"
        character = Character(id=character_id, name=character_name, player_id=player.id)
        match.characters.append(character)
        player.character_id = character_id
        game_state_service.register_player_character(player.id, character_id)
    
    logger.info(f"创建测试游戏: 房间={room.name} (ID: {room_id}), 场景={scene}, 剧本ID={scenario_id}")
    
    return {
        "match_id": match.id,
        "status": match.status,
        "scene": match.scene,
        "scenario_id": match.scenario_id,
        "characters": [{"id": c.id, "name": c.name, "player_id": c.player_id} for c in match.characters]
    }

# 创建测试回合
@router.post("/create_test_turn", response_model=Dict[str, Any])
async def create_test_turn(
    turn_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """在指定游戏中创建测试回合，可以指定回合类型、状态等"""
    if not game_state_service or not match_service or not turn_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_id = turn_data.get("room_id")
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
    
    turn_type = turn_data.get("turn_type", TurnType.DM)
    turn_status = turn_data.get("status", TurnStatus.PENDING)
    
    # 创建回合
    turn_id = str(uuid.uuid4())
    
    if turn_type == TurnType.DM:
        narration = turn_data.get("narration", "这是一个测试DM回合")
        turn = DMTurn(
            id=turn_id,
            turn_type=turn_type,
            status=turn_status,
            narration=narration
        )
        
        # 设置下一回合信息
        next_turn_type = turn_data.get("next_turn_type", TurnType.PLAYER)
        active_players = turn_data.get("active_players", [p.id for p in room.players])
        turn.next_turn_info = NextTurnInfo(
            turn_type=next_turn_type,
            active_players=active_players
        )
    
    elif turn_type == TurnType.PLAYER:
        active_players = turn_data.get("active_players", [p.id for p in room.players])
        is_dice_turn = turn_data.get("is_dice_turn", False)
        
        if is_dice_turn:
            difficulty = turn_data.get("difficulty", 10)
            action_desc = turn_data.get("action_desc", "测试检定")
            turn = DiceTurn(
                id=turn_id,
                turn_type=turn_type,
                status=turn_status,
                active_players=active_players,
                difficulty=difficulty,
                action_desc=action_desc
            )
        else:
            turn = ActionTurn(
                id=turn_id,
                turn_type=turn_type,
                status=turn_status,
                active_players=active_players
            )
    
    # 添加到游戏局
    match.turns.append(turn)
    match.current_turn_id = turn_id
    
    logger.info(f"创建测试回合: 类型={turn_type}, 状态={turn_status}, 游戏={match.id}")
    
    return {
        "turn_id": turn.id,
        "turn_type": turn.turn_type,
        "status": turn.status,
        "active_players": getattr(turn, "active_players", []) if turn_type == TurnType.PLAYER else [],
        "next_turn_info": {
            "turn_type": turn.next_turn_info.turn_type,
            "active_players": turn.next_turn_info.active_players
        } if turn.next_turn_info else None
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
        from core.controllers.turn_controller import TurnController
        turn_controller = TurnController(turn)
        
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
        from core.controllers.turn_controller import TurnController
        turn_controller = TurnController(turn)
        
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

# 模拟DM回合
@router.post("/simulate_dm_turn", response_model=Dict[str, Any])
async def simulate_dm_turn(
    dm_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user)
):
    """模拟DM回合，生成叙述并指定下一回合的活跃玩家"""
    if not game_state_service or not turn_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_id = dm_data.get("room_id")
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
    
    if turn.turn_type != TurnType.DM:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不是DM回合"
        )
    
    narration = dm_data.get("narration", "这是一个测试DM叙述")
    next_turn_type = dm_data.get("next_turn_type", TurnType.PLAYER)
    active_players = dm_data.get("active_players", [p.id for p in room.players])
    is_dice_turn = dm_data.get("is_dice_turn", False)
    
    # 更新DM回合
    from core.controllers.turn_controller import TurnController
    turn_controller = TurnController(turn)
    
    # 设置叙述
    turn.narration = narration
    
    # 设置下一回合信息
    turn.next_turn_info = NextTurnInfo(
        turn_type=next_turn_type,
        active_players=active_players
    )
    
    # 完成当前回合
    turn.status = TurnStatus.COMPLETED
    turn.completed_at = datetime.now()
    
    # 创建下一个回合
    next_turn_id = str(uuid.uuid4())
    
    if next_turn_type == TurnType.PLAYER:
        if is_dice_turn:
            difficulty = dm_data.get("difficulty", 10)
            action_desc = dm_data.get("action_desc", "测试检定")
            next_turn = DiceTurn(
                id=next_turn_id,
                turn_type=next_turn_type,
                status=TurnStatus.PENDING,
                active_players=active_players,
                difficulty=difficulty,
                action_desc=action_desc
            )
        else:
            next_turn = ActionTurn(
                id=next_turn_id,
                turn_type=next_turn_type,
                status=TurnStatus.PENDING,
                active_players=active_players
            )
    else:
        next_turn = DMTurn(
            id=next_turn_id,
            turn_type=next_turn_type,
            status=TurnStatus.PENDING
        )
    
    # 添加到游戏局
    match.turns.append(next_turn)
    match.current_turn_id = next_turn_id
    
    logger.info(f"模拟DM回合: 叙述长度={len(narration)}, 下一回合类型={next_turn_type}, 活跃玩家={active_players}")
    
    return {
        "success": True,
        "narration": narration,
        "next_turn": {
            "id": next_turn.id,
            "turn_type": next_turn.turn_type,
            "active_players": getattr(next_turn, "active_players", []) if next_turn_type == TurnType.PLAYER else [],
            "is_dice_turn": is_dice_turn,
            "difficulty": getattr(next_turn, "difficulty", None) if is_dice_turn else None,
            "action_desc": getattr(next_turn, "action_desc", None) if is_dice_turn else None
        }
    }

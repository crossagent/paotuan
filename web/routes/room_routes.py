from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
import uuid
import logging

from web.routes.user_routes import get_current_user
from web.auth import User
from models.entities import Room as GameRoom

# 创建路由器
router = APIRouter(
    prefix="/api/rooms",
    tags=["rooms"],
    responses={404: {"description": "Not found"}},
)

# 配置日志
logger = logging.getLogger(__name__)

# 房间数据模型
class RoomInfo:
    """房间信息模型"""
    def __init__(self, room: GameRoom):
        self.id = room.id
        self.name = room.name
        self.created_at = room.created_at
        self.player_count = len(room.players)
        self.has_active_match = room.current_match_id is not None
        self.settings = room.settings

# 全局游戏实例引用
game_instance = None

# 设置游戏实例
def set_game_instance(instance):
    global game_instance
    game_instance = instance

# 获取房间列表
@router.get("/", response_model=List[Dict[str, Any]])
async def list_rooms(current_user: User = Depends(get_current_user)):
    """获取房间列表"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    rooms = []
    for room_id, room in game_instance.rooms.items():
        room_info = RoomInfo(room)
        rooms.append({
            "id": room_info.id,
            "name": room_info.name,
            "created_at": room_info.created_at,
            "player_count": room_info.player_count,
            "has_active_match": room_info.has_active_match
        })
    
    return rooms

# 创建房间
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """创建新房间"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_name = room_data.get("name", f"{current_user.username}的房间")
    
    # 创建房间
    room_id = str(uuid.uuid4())
    room = GameRoom(id=room_id, name=room_name)
    
    # 添加到游戏实例
    game_instance.rooms[room_id] = room
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 将创建者添加到房间
    player = room_manager.add_player(current_user.id, current_user.username)
    
    logger.info(f"创建房间: {room_name} (ID: {room_id}), 创建者: {current_user.username}")
    
    return {
        "id": room.id,
        "name": room.name,
        "created_at": room.created_at,
        "player_count": len(room.players),
        "has_active_match": room.current_match_id is not None
    }

# 获取房间详情
@router.get("/{room_id}", response_model=Dict[str, Any])
async def get_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取房间详情"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 获取当前游戏局
    current_match = room_manager.get_current_match()
    
    # 构建玩家列表
    players = []
    for player in room.players:
        players.append({
            "id": player.id,
            "name": player.name,
            "joined_at": player.joined_at,
            "health": player.health,
            "alive": player.alive,
            "location": player.location
        })
    
    return {
        "id": room.id,
        "name": room.name,
        "created_at": room.created_at,
        "players": players,
        "current_match": {
            "id": current_match.id,
            "status": current_match.status,
            "scene": current_match.scene,
            "created_at": current_match.created_at
        } if current_match else None,
        "settings": room.settings
    }

# 加入房间
@router.post("/{room_id}/join", response_model=Dict[str, Any])
async def join_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """加入房间"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 将玩家添加到房间
    player = room_manager.add_player(current_user.id, current_user.username)
    
    logger.info(f"玩家加入房间: {current_user.username} (ID: {current_user.id}), 房间: {room.name} (ID: {room_id})")
    
    return {
        "id": room.id,
        "name": room.name,
        "player": {
            "id": player.id,
            "name": player.name
        }
    }

# 离开房间
@router.post("/{room_id}/leave", response_model=Dict[str, Any])
async def leave_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """离开房间"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 将玩家从房间中移除
    success = room_manager.remove_player(current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="玩家不在房间中"
        )
    
    logger.info(f"玩家离开房间: {current_user.username} (ID: {current_user.id}), 房间: {room.name} (ID: {room_id})")
    
    return {
        "success": True,
        "message": f"已离开房间: {room.name}"
    }

# 开始游戏
@router.post("/{room_id}/start", response_model=Dict[str, Any])
async def start_game(
    room_id: str,
    game_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """开始游戏"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 检查是否有进行中的游戏
    current_match = room_manager.get_current_match()
    if current_match and current_match.status == "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已有进行中的游戏"
        )
    
    # 获取场景和剧本ID
    scene = game_data.get("scene", "默认场景")
    scenario_id = game_data.get("scenario_id")
    
    try:
        # 创建新游戏局
        match = room_manager.create_match(scene)
        
        # 如果指定了剧本，设置剧本
        if scenario_id:
            success = room_manager.set_scenario(scenario_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"设置剧本失败: {scenario_id}"
                )
        
        # 更新游戏状态
        from models.entities import GameStatus
        match.status = GameStatus.RUNNING
        
        logger.info(f"开始游戏: 房间={room.name} (ID: {room_id}), 场景={scene}, 剧本ID={scenario_id}")
        
        return {
            "match_id": match.id,
            "status": match.status,
            "scene": match.scene,
            "scenario_id": match.scenario_id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

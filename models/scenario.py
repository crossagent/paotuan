from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

class KeyItem(BaseModel):
    """关键道具模型"""
    position: str = Field(..., description="道具位置")
    item: str = Field(..., description="道具名称")
    collected: bool = Field(default=False, description="是否已被收集")

class Room(BaseModel):
    """房间模型"""
    name: str = Field(..., description="房间名称")
    description: str = Field(..., description="房间描述")
    key_items: List[KeyItem] = Field(default_factory=list, description="房间内的关键道具")
    discovered: bool = Field(default=False, description="玩家是否已发现该房间")
    visited: bool = Field(default=False, description="玩家是否已访问该房间")

class Floor(BaseModel):
    """楼层模型"""
    name: str = Field(..., description="楼层名称")
    description: str = Field(..., description="楼层描述")
    rooms: List[Room] = Field(default_factory=list, description="楼层内的房间")
    discovered: bool = Field(default=False, description="玩家是否已发现该楼层")
    
class Map(BaseModel):
    """地图模型"""
    floors: List[Floor] = Field(default_factory=list, description="地图楼层")

class NPC(BaseModel):
    """NPC角色模型"""
    name: str = Field(..., description="NPC名称")
    description: str = Field(..., description="NPC描述")
    location: Optional[str] = Field(None, description="NPC当前位置，格式为'楼层/房间'")
    encountered: bool = Field(default=False, description="玩家是否已遇到该NPC")

class Scenario(BaseModel):
    """剧本模型"""
    id: str = Field(..., description="剧本唯一标识符")
    name: str = Field(..., description="剧本名称")
    goal: str = Field(..., description="游戏目标")
    scene: str = Field(..., description="场景概述描述")
    map: Map = Field(..., description="场景地图")
    key_items: List[str] = Field(default_factory=list, description="关键道具列表")
    character_settings: Dict[str, Any] = Field(..., description="角色设定")
    npcs: List[NPC] = Field(default_factory=list, description="NPC列表") 
    plot_points: List[str] = Field(default_factory=list, description="剧情节点大纲")
    challenges: List[str] = Field(default_factory=list, description="冲突与挑战")
    background: str = Field(..., description="背景故事")
    clues: List[str] = Field(default_factory=list, description="线索与信息")
    pacing: str = Field(default="", description="节奏与时间设定")
    rules: str = Field(default="", description="规则与限制")
    current_plot_point: int = Field(default=0, description="当前剧情节点索引")
    # 玩家当前位置，格式为"楼层/房间"
    player_location: str = Field(default="", description="玩家当前位置")
    # 已收集的道具
    collected_items: List[str] = Field(default_factory=list, description="已收集的道具")

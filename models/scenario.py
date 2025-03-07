from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

class CharacterTemplate(BaseModel):
    """角色模板模型"""
    name: str = Field(..., description="角色名称")
    occupation: str = Field(..., description="角色职业")
    description: str = Field("", description="角色描述")

class Puzzle(BaseModel):
    """谜题模型"""
    name: str = Field(..., description="谜题名称")
    content: str = Field(..., description="谜题内容")
    possible_items: List[str] = Field(default_factory=list, description="可能包含的道具")

class Scene(BaseModel):
    """场景模型"""
    name: str = Field(..., description="场景名称")
    description: str = Field(..., description="场景描述")
    puzzle: Optional[Puzzle] = Field(None, description="场景中的谜题")
    discovered: bool = Field(default=False, description="玩家是否已发现该场景")
    visited: bool = Field(default=False, description="玩家是否已访问该场景")

class Character(BaseModel):
    """角色模型"""
    name: str = Field(..., description="角色名称")
    description: str = Field(..., description="角色描述")
    is_main: bool = Field(default=True, description="是否为主要角色")
    action_goal: Optional[str] = Field(None, description="行动目标")
    location: Optional[str] = Field(None, description="角色当前位置")
    encountered: bool = Field(default=False, description="玩家是否已遇到该角色")

class Event(BaseModel):
    """事件模型"""
    name: str = Field(..., description="事件名称")
    content: str = Field(..., description="事件内容")
    characters: List[Character] = Field(default_factory=list, description="事件中的角色")

class Scenario(BaseModel):
    """剧本模型"""
    id: str = Field(..., description="剧本唯一标识符")
    name: str = Field(default="疯人院", description="剧本名称")
    victory_conditions: List[str] = Field(default_factory=list, description="胜利条件")
    failure_conditions: List[str] = Field(default_factory=list, description="失败条件")
    min_players: int = Field(default=1, description="最少所需玩家数")
    max_players: int = Field(default=4, description="最多支持玩家数")
    character_templates: List[CharacterTemplate] = Field(default_factory=list, description="角色模板列表")
    game_over: bool = Field(default=False, description="游戏是否结束")
    game_result: Optional[Literal["victory", "failure"]] = Field(None, description="游戏结果")
    world_background: str = Field(default="", description="世界背景")
    main_scene: str = Field(default="", description="主要场景")
    scenes: List[Scene] = Field(default_factory=list, description="场景列表")
    characters: List[Character] = Field(default_factory=list, description="角色列表")
    events: List[Event] = Field(default_factory=list, description="事件列表")
    current_event_index: int = Field(default=0, description="当前事件索引")
    player_location: str = Field(default="", description="玩家当前位置")
    collected_items: List[str] = Field(default_factory=list, description="已收集的道具")

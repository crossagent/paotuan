import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from models.scenario import Scenario, Floor, Room, KeyItem, Map, NPC

logger = logging.getLogger(__name__)

class ScenarioLoader:
    """剧本加载器"""
    
    def __init__(self, scenarios_dir: str = "story/scenarios"):
        """初始化剧本加载器
        
        Args:
            scenarios_dir: 剧本JSON文件所在的目录
        """
        self.scenarios_dir = scenarios_dir
        # 确保剧本目录存在
        os.makedirs(scenarios_dir, exist_ok=True)
        
    def load_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """加载指定ID的剧本
        
        Args:
            scenario_id: 剧本ID
            
        Returns:
            加载的剧本对象，如果不存在则返回None
        """
        try:
            file_path = os.path.join(self.scenarios_dir, f"{scenario_id}.json")
            if not os.path.exists(file_path):
                logger.error(f"剧本文件不存在: {file_path}")
                return None
                
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
                # 预处理地图数据
                map_data = self._process_map_data(data.get("场景地图", []))
                
                # 预处理NPC数据
                npcs_data = []
                if "角色设定" in data and "NPC" in data["角色设定"]:
                    for npc_data in data["角色设定"]["NPC"]:
                        npcs_data.append(NPC(
                            name=npc_data["名称"],
                            description=npc_data["描述"],
                            location=npc_data.get("位置", None)
                        ))
                
                # 创建场景对象
                scenario = Scenario(
                    id=scenario_id,
                    name=data.get("剧本名称", "未命名剧本"),
                    goal=data.get("目标", ""),
                    scene=data.get("场景", ""),
                    map=map_data,
                    key_items=data.get("关键道具", []),
                    character_settings=data.get("角色设定", {}),
                    npcs=npcs_data,
                    plot_points=data.get("剧情节点", []),
                    challenges=data.get("冲突与挑战", []),
                    background=data.get("背景故事", ""),
                    clues=data.get("线索与信息", []),
                    pacing=data.get("节奏与时间设定", ""),
                    rules=data.get("规则与限制", ""),
                    player_location="一楼/大堂"  # 默认起始位置
                )
                
                return scenario
                
        except Exception as e:
            logger.exception(f"加载剧本失败: {str(e)}")
            return None
    
    def _process_map_data(self, map_data) -> Map:
        """处理地图数据
        
        Args:
            map_data: 原始地图数据
            
        Returns:
            处理后的Map对象
        """
        floors = []
        
        for floor_data in map_data:
            rooms = []
            
            for room_data in floor_data.get("房间", []):
                key_items = []
                
                for item_data in room_data.get("关键道具", []):
                    key_items.append(KeyItem(
                        position=item_data["位置"],
                        item=item_data["道具"]
                    ))
                
                rooms.append(Room(
                    name=room_data["名称"],
                    description=room_data["描述"],
                    key_items=key_items
                ))
            
            floors.append(Floor(
                name=floor_data["楼层"],
                description=floor_data["描述"],
                rooms=rooms
            ))
        
        return Map(floors=floors)
    
    def list_scenarios(self) -> List[Dict[str, str]]:
        """列出所有可用的剧本
        
        Returns:
            剧本列表，每个剧本包含id和name
        """
        scenarios = []
        try:
            # 遍历剧本目录中的所有JSON文件
            for filename in os.listdir(self.scenarios_dir):
                if filename.endswith('.json'):
                    scenario_id = filename[:-5]  # 移除.json后缀
                    file_path = os.path.join(self.scenarios_dir, filename)
                    
                    with open(file_path, 'r', encoding='utf-8') as file:
                        data = json.load(file)
                        scenarios.append({
                            "id": scenario_id,
                            "name": data.get("剧本名称", "未命名剧本")
                        })
        except Exception as e:
            logger.exception(f"列出剧本失败: {str(e)}")
        
        return scenarios
            
    def save_scenario(self, scenario: Scenario) -> bool:
        """保存剧本到文件
        
        Args:
            scenario: 要保存的剧本对象
            
        Returns:
            是否保存成功
        """
        try:
            file_path = os.path.join(self.scenarios_dir, f"{scenario.id}.json")
            
            # 将Scenario对象转换为dict并保存为JSON
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(scenario.dict(), file, ensure_ascii=False, indent=2)
                
            return True
        except Exception as e:
            logger.exception(f"保存剧本失败: {str(e)}")
            return False
    
    def get_location_description(self, scenario: Scenario) -> Tuple[str, List[Dict[str, str]]]:
        """获取当前位置的描述和可见道具
        
        Args:
            scenario: 剧本对象
            
        Returns:
            当前位置的描述和可见道具列表
        """
        if not scenario.player_location:
            return "", []
            
        # 获取当前位置
        floor_name, room_name = scenario.player_location.split("/")
        
        # 查找楼层和房间
        for floor in scenario.map.floors:
            if floor.name == floor_name:
                for room in floor.rooms:
                    if room.name == room_name:
                        # 整合房间描述
                        description = f"{floor.description} - {room.description}"
                        
                        # 获取未收集的道具
                        visible_items = []
                        for key_item in room.key_items:
                            if not key_item.collected:
                                visible_items.append({
                                    "position": key_item.position,
                                    "item": key_item.item
                                })
                        
                        return description, visible_items
                        
        return "", []

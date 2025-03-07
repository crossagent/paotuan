import os
import json
import logging
from typing import List, Dict, Optional, Tuple, Any
from models.scenario import Scenario, Scene, Puzzle, Character, Event, CharacterTemplate

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
                
                # 检查剧本格式是否正确
                if "玩家人数" not in data:
                    logger.error(f"剧本格式错误: 缺少玩家人数设置")
                    return None
                
                # 获取玩家人数限制
                min_players = data.get("玩家人数", {}).get("最少")
                max_players = data.get("玩家人数", {}).get("最多")
                
                if min_players is None or max_players is None:
                    logger.error(f"剧本格式错误: 玩家人数设置不完整")
                    return None
                
                # 处理场景数据
                scenes = self._process_scenes_data(data.get("地图与谜题设置", []))
                
                # 处理角色数据
                characters = self._process_characters_data(data.get("重要角色", {}))
                
                # 处理事件数据
                events = self._process_events_data(data.get("事件脉络", []))
                
                # 处理角色模板数据
                character_templates = self._process_character_templates(data.get("角色模板", []))
                
                # 创建场景对象
                scenario = Scenario(
                    id=scenario_id,
                    name="疯人院",
                    victory_conditions=data.get("胜利条件", []),
                    failure_conditions=data.get("失败条件", []),
                    min_players=min_players,
                    max_players=max_players,
                    character_templates=character_templates,
                    world_background=data.get("世界背景与主要场景", {}).get("世界背景", ""),
                    main_scene=data.get("世界背景与主要场景", {}).get("主要场景", ""),
                    scenes=scenes,
                    characters=characters,
                    events=events,
                    player_location="入口大厅"  # 默认起始位置
                )
                
                return scenario
                
        except Exception as e:
            logger.exception(f"加载剧本失败: {str(e)}")
            return None
    
    def _process_scenes_data(self, scenes_data: List[Dict[str, Any]]) -> List[Scene]:
        """处理场景与谜题数据
        
        Args:
            scenes_data: 原始场景数据
            
        Returns:
            处理后的Scene对象列表
        """
        scenes = []
        
        for scene_data in scenes_data:
            puzzle = None
            if "谜题" in scene_data:
                puzzle_data = scene_data["谜题"]
                puzzle = Puzzle(
                    name=puzzle_data.get("谜题名称", ""),
                    content=puzzle_data.get("谜题内容", ""),
                    possible_items=puzzle_data.get("可能包含的道具", [])
                )
            
            scenes.append(Scene(
                name=scene_data.get("场景名称", ""),
                description=scene_data.get("场景描述", ""),
                puzzle=puzzle
            ))
        
        return scenes
    
    def _process_characters_data(self, characters_data: Dict[str, Any]) -> List[Character]:
        """处理角色数据
        
        Args:
            characters_data: 原始角色数据
            
        Returns:
            处理后的Character对象列表
        """
        characters = []
        
        # 处理主要角色
        if "主要角色" in characters_data:
            for char_data in characters_data["主要角色"]:
                characters.append(Character(
                    name=char_data.get("角色名称", ""),
                    description=char_data.get("描述", ""),
                    is_main=True
                ))
        
        # 处理次要角色
        if "次要角色" in characters_data:
            for char_data in characters_data["次要角色"]:
                characters.append(Character(
                    name=char_data.get("角色名称", ""),
                    description=char_data.get("描述", ""),
                    is_main=False
                ))
        
        return characters
    
    def _process_character_templates(self, templates_data: List[Dict[str, Any]]) -> List[CharacterTemplate]:
        """处理角色模板数据
        
        Args:
            templates_data: 原始角色模板数据
            
        Returns:
            处理后的CharacterTemplate对象列表
        """
        templates = []
        
        for template_data in templates_data:
            templates.append(CharacterTemplate(
                name=template_data.get("姓名", ""),
                occupation=template_data.get("职业", ""),
                description=template_data.get("描述", "")
            ))
        
        return templates
    
    def _process_events_data(self, events_data: List[Dict[str, Any]]) -> List[Event]:
        """处理事件数据
        
        Args:
            events_data: 原始事件数据
            
        Returns:
            处理后的Event对象列表
        """
        events = []
        
        for event_data in events_data:
            event_characters = []
            
            # 处理事件中的角色
            if "事件目标" in event_data:
                # 主要角色
                if "登场角色" in event_data["事件目标"]:
                    for char_data in event_data["事件目标"]["登场角色"]:
                        event_characters.append(Character(
                            name=char_data.get("角色名称", ""),
                            description="",  # 事件中角色无需重复描述
                            is_main=True,
                            action_goal=char_data.get("行动目标", "")
                        ))
                
                # 次要角色
                if "次要角色" in event_data["事件目标"]:
                    for char_data in event_data["事件目标"]["次要角色"]:
                        event_characters.append(Character(
                            name=char_data.get("角色名称", ""),
                            description="",  # 事件中角色无需重复描述
                            is_main=False,
                            action_goal=char_data.get("行动目标", "")
                        ))
            
            events.append(Event(
                name=event_data.get("事件名称", ""),
                content=event_data.get("事件内容", ""),
                characters=event_characters
            ))
        
        return events
    
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
                            "name": data.get("剧本名称", "疯人院")
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
            
        # 查找当前场景
        current_scene = None
        for scene in scenario.scenes:
            if scene.name == scenario.player_location:
                current_scene = scene
                break
                
        if not current_scene:
            return "", []
            
        # 返回场景描述和可能的道具
        possible_items = []
        if current_scene.puzzle:
            for item in current_scene.puzzle.possible_items:
                if item not in scenario.collected_items:
                    possible_items.append({
                        "position": current_scene.name,
                        "item": item
                    })
                    
        return current_scene.description, possible_items
